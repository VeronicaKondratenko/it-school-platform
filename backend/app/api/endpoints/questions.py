"""Structured student questions / appeals module.

This module deliberately lives next to the existing `messages` endpoints instead
of replacing them. It adds a safer workflow with statuses, recipients, replies,
AI-history and notifications without breaking the old teacher inbox.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ...auth import get_current_user, get_current_admin
from ...database import get_db
from ...models import (
    Course,
    Notification,
    QuestionMessage,
    QuestionThread,
    StudyGroup,
    User,
    UserRole,
)
from ...schemas import (
    NotificationResponse,
    QuestionAssignRequest,
    QuestionCreate,
    QuestionMessageResponse,
    QuestionReplyCreate,
    QuestionThreadResponse,
)
from ..access import get_teacher_course_ids

router = APIRouter()

VALID_STATUSES = {"new", "waiting_answer", "answered", "closed"}
VALID_TARGETS = {"admin", "teacher", "ai"}


def _role_value(user: User) -> str:
    role = getattr(user, "role", "")
    return getattr(role, "value", str(role))


async def _notify(db: AsyncSession, user_id: Optional[int], title: str, body: str, link: str) -> None:
    if not user_id:
        return
    db.add(Notification(user_id=user_id, title=title[:180], body=body[:1000], link=link))


async def _notify_admins(db: AsyncSession, title: str, body: str, link: str) -> None:
    result = await db.execute(select(User.id).where(User.role == UserRole.admin))
    for row in result.all():
        await _notify(db, row[0], title, body, link)


async def _student_group_for_course(db: AsyncSession, student_id: int, course_id: int) -> Optional[StudyGroup]:
    # NOTE: must stay consistent with /api/student/courses, which lists the
    # student's courses WITHOUT an is_active filter. Requiring is_active here
    # caused a trap: a course shown in the dropdown could be rejected on submit
    # with 403. We therefore match any group the student belongs to that has the
    # course, preferring active groups for teacher resolution.
    result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(
            User.id == student_id,
            StudyGroup.courses.any(Course.id == course_id),
        )
        .options(selectinload(StudyGroup.courses), selectinload(StudyGroup.teacher))
        .order_by(StudyGroup.is_active.desc())
    )
    return result.scalars().first()


async def _load_thread(db: AsyncSession, thread_id: int) -> QuestionThread:
    result = await db.execute(
        select(QuestionThread)
        .where(QuestionThread.id == thread_id)
        .options(
            selectinload(QuestionThread.student),
            selectinload(QuestionThread.target_user),
            selectinload(QuestionThread.course),
            selectinload(QuestionThread.messages).selectinload(QuestionMessage.sender),
        )
    )
    thread = result.scalars().first()
    if not thread:
        raise HTTPException(status_code=404, detail="Question thread not found")
    return thread


def _message_to_response(msg: QuestionMessage) -> QuestionMessageResponse:
    sender_name = None
    if msg.sender:
        sender_name = msg.sender.full_name or msg.sender.email
    elif msg.sender_role == "ai":
        sender_name = "IT School AI"
    return QuestionMessageResponse(
        id=msg.id,
        sender_id=msg.sender_id,
        sender_role=msg.sender_role,
        sender_name=sender_name,
        message_text=msg.message_text,
        is_ai_response=bool(msg.is_ai_response),
        created_at=msg.created_at,
    )


def _thread_to_response(thread: QuestionThread, include_messages: bool = False) -> QuestionThreadResponse:
    messages = list(thread.messages or [])
    last_message = messages[-1].message_text if messages else None
    return QuestionThreadResponse(
        id=thread.id,
        student_id=thread.student_id,
        student_name=(thread.student.full_name if thread.student else None),
        student_email=(thread.student.email if thread.student else None),
        target_type=thread.target_type,
        target_user_id=thread.target_user_id,
        target_name=(thread.target_user.full_name if thread.target_user else None),
        target_email=(thread.target_user.email if thread.target_user else None),
        course_id=thread.course_id,
        course_title=(thread.course.title if thread.course else None),
        title=thread.title,
        category=thread.category,
        status=thread.status,
        priority=thread.priority,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        closed_at=thread.closed_at,
        last_message=last_message,
        messages_count=len(messages),
        messages=[_message_to_response(m) for m in messages] if include_messages else [],
    )


async def _assert_can_view(db: AsyncSession, user: User, thread: QuestionThread) -> None:
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.student and thread.student_id == user.id:
        return
    if user.role == UserRole.teacher and thread.target_type == "teacher" and thread.target_user_id == user.id:
        return
    raise HTTPException(status_code=403, detail="You do not have access to this question")


async def _assert_can_reply(db: AsyncSession, user: User, thread: QuestionThread) -> None:
    if thread.status == "closed":
        raise HTTPException(status_code=400, detail="Question is closed")
    await _assert_can_view(db, user, thread)
    if thread.target_type == "ai":
        raise HTTPException(status_code=400, detail="AI history cannot be replied to here")


@router.post("", response_model=QuestionThreadResponse)
async def create_question(
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Student creates a question for an administrator or a teacher."""
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Лише студенти можуть створювати питання")

    target_type = payload.target_type.strip().lower()
    target_user_id = payload.target_user_id
    course_id = payload.course_id

    if target_type == "teacher":
        if not course_id:
            raise HTTPException(status_code=400, detail="Для питання викладачу потрібно обрати курс")
        group = await _student_group_for_course(db, current_user.id, course_id)
        if not group:
            raise HTTPException(status_code=403, detail="Вас не записано на цей курс, тому написати викладачу не можна")
        if target_user_id is None:
            target_user_id = group.teacher_id
        if not target_user_id:
            raise HTTPException(status_code=400, detail="Для цього курсу не призначено викладача — напишіть адміністратору")
        if group.teacher_id != target_user_id:
            # Keep the first version safe: student may write only to the teacher of their group/course.
            raise HTTPException(status_code=403, detail="Обраний викладач не веде цей курс для вашої групи")

    if target_type == "admin":
        target_user_id = None

    thread = QuestionThread(
        student_id=current_user.id,
        target_type=target_type,
        target_user_id=target_user_id,
        course_id=course_id,
        title=payload.title.strip(),
        category=(payload.category or "general").strip()[:80],
        status="new",
        priority=payload.priority,
    )
    db.add(thread)
    await db.flush()

    db.add(QuestionMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        sender_role="student",
        message_text=payload.message.strip(),
        is_ai_response=False,
    ))

    link = "/questions.html"
    if target_type == "teacher":
        await _notify(db, target_user_id, "Нове питання від студента", payload.title.strip(), "/teacher-questions.html")
    else:
        await _notify_admins(db, "Нове звернення до адміністратора", payload.title.strip(), "/admin-questions.html")

    await db.commit()
    return _thread_to_response(await _load_thread(db, thread.id), include_messages=True)


@router.get("/my", response_model=list[QuestionThreadResponse])
async def my_questions(
    include_ai: bool = Query(default=True),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Only students can access this list")
    stmt = (
        select(QuestionThread)
        .where(QuestionThread.student_id == current_user.id)
        .options(
            selectinload(QuestionThread.student),
            selectinload(QuestionThread.target_user),
            selectinload(QuestionThread.course),
            selectinload(QuestionThread.messages).selectinload(QuestionMessage.sender),
        )
        .order_by(desc(QuestionThread.updated_at), desc(QuestionThread.created_at))
    )
    if not include_ai:
        stmt = stmt.where(QuestionThread.target_type != "ai")
    if status_filter:
        stmt = stmt.where(QuestionThread.status == status_filter)
    result = await db.execute(stmt)
    return [_thread_to_response(t) for t in result.scalars().all()]


@router.get("/teacher", response_model=list[QuestionThreadResponse])
async def teacher_questions(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.teacher:
        raise HTTPException(status_code=403, detail="Teacher access required")
    stmt = (
        select(QuestionThread)
        .where(
            QuestionThread.target_type == "teacher",
            QuestionThread.target_user_id == current_user.id,
        )
        .options(
            selectinload(QuestionThread.student),
            selectinload(QuestionThread.target_user),
            selectinload(QuestionThread.course),
            selectinload(QuestionThread.messages).selectinload(QuestionMessage.sender),
        )
        .order_by(desc(QuestionThread.priority), desc(QuestionThread.updated_at), desc(QuestionThread.created_at))
    )
    if status_filter:
        stmt = stmt.where(QuestionThread.status == status_filter)
    result = await db.execute(stmt)
    return [_thread_to_response(t) for t in result.scalars().all()]


@router.get("/admin", response_model=list[QuestionThreadResponse])
async def admin_questions(
    target_type: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    stmt = (
        select(QuestionThread)
        .options(
            selectinload(QuestionThread.student),
            selectinload(QuestionThread.target_user),
            selectinload(QuestionThread.course),
            selectinload(QuestionThread.messages).selectinload(QuestionMessage.sender),
        )
        .order_by(desc(QuestionThread.priority), desc(QuestionThread.updated_at), desc(QuestionThread.created_at))
    )
    if target_type and target_type in VALID_TARGETS:
        stmt = stmt.where(QuestionThread.target_type == target_type)
    if status_filter and status_filter in VALID_STATUSES:
        stmt = stmt.where(QuestionThread.status == status_filter)
    result = await db.execute(stmt)
    return [_thread_to_response(t) for t in result.scalars().all()]


@router.get("/admin/stats/summary")
async def questions_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    result = await db.execute(
        select(QuestionThread.target_type, QuestionThread.status, func.count(QuestionThread.id))
        .group_by(QuestionThread.target_type, QuestionThread.status)
    )
    return {"items": [{"target_type": r[0], "status": r[1], "count": r[2]} for r in result.all()]}


@router.get("/{thread_id}", response_model=QuestionThreadResponse)
async def question_details(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await _load_thread(db, thread_id)
    await _assert_can_view(db, current_user, thread)
    return _thread_to_response(thread, include_messages=True)


@router.post("/{thread_id}/reply", response_model=QuestionThreadResponse)
async def reply_question(
    thread_id: int,
    payload: QuestionReplyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await _load_thread(db, thread_id)
    await _assert_can_reply(db, current_user, thread)

    sender_role = _role_value(current_user)
    db.add(QuestionMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        sender_role=sender_role,
        message_text=payload.message.strip(),
        is_ai_response=False,
    ))

    if current_user.role == UserRole.student:
        thread.status = "waiting_answer"
        if thread.target_type == "teacher":
            await _notify(db, thread.target_user_id, "Студент уточнив питання", thread.title, "/teacher-questions.html")
        elif thread.target_type == "admin":
            await _notify_admins(db, "Студент уточнив звернення", thread.title, "/admin-questions.html")
    else:
        thread.status = "answered"
        await _notify(db, thread.student_id, "Нова відповідь на ваше питання", thread.title, "/questions.html")

    thread.updated_at = datetime.utcnow()
    await db.commit()
    return _thread_to_response(await _load_thread(db, thread.id), include_messages=True)


@router.patch("/{thread_id}/close", response_model=QuestionThreadResponse)
async def close_question(
    thread_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    thread = await _load_thread(db, thread_id)
    await _assert_can_view(db, current_user, thread)
    thread.status = "closed"
    thread.closed_at = datetime.utcnow()
    thread.updated_at = datetime.utcnow()
    if current_user.id != thread.student_id:
        await _notify(db, thread.student_id, "Питання закрито", thread.title, "/questions.html")
    await db.commit()
    return _thread_to_response(await _load_thread(db, thread.id), include_messages=True)


@router.patch("/{thread_id}/assign", response_model=QuestionThreadResponse)
async def assign_question(
    thread_id: int,
    payload: QuestionAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin),
):
    thread = await _load_thread(db, thread_id)
    if payload.target_type == "teacher" and not payload.target_user_id:
        raise HTTPException(status_code=400, detail="target_user_id is required for teacher assignment")
    thread.target_type = payload.target_type
    thread.target_user_id = payload.target_user_id if payload.target_type == "teacher" else None
    if payload.course_id is not None:
        thread.course_id = payload.course_id
    thread.status = "waiting_answer"
    thread.updated_at = datetime.utcnow()
    if thread.target_type == "teacher":
        await _notify(db, thread.target_user_id, "Адміністратор передав вам питання", thread.title, "/teacher-questions.html")
    else:
        await _notify_admins(db, "Звернення призначено адміністрації", thread.title, "/admin-questions.html")
    await _notify(db, thread.student_id, "Ваше питання перенаправлено", thread.title, "/questions.html")
    await db.commit()
    return _thread_to_response(await _load_thread(db, thread.id), include_messages=True)
