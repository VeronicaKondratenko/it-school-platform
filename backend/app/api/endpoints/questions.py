"""Structured student questions / appeals module.

This module deliberately lives next to the existing `messages` endpoints instead
of replacing them. It adds a safer workflow with statuses, recipients, replies,
AI-history and notifications without breaking the old teacher inbox.
"""
from __future__ import annotations

from datetime import datetime
import logging
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
    Discipline,
    Schedule,
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
logger = logging.getLogger(__name__)

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


def _short_text(text: str, limit: int = 2800) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


async def _send_telegram_message(db: AsyncSession, user_id: Optional[int], text: str) -> None:
    """Send an optional Telegram notification to a linked user.

    Web notifications are the source of truth. Telegram delivery must never break
    question replies, because a user might not have linked Telegram, the bot might
    be disabled in a local environment, or Telegram can temporarily reject the
    request. Therefore this helper logs and silently continues on failure.
    """
    if not user_id:
        return
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalars().first()
    telegram_id = getattr(target, "telegram_id", None) if target else None
    if not telegram_id:
        return
    try:
        from ...bot import bot  # imported lazily to avoid startup circular imports
        if not bot:
            logger.info("Telegram bot is not initialized; skipped message for user_id=%s", user_id)
            return
        await bot.send_message(chat_id=int(telegram_id), text=_short_text(text))
    except Exception as exc:
        logger.warning("Could not send Telegram notification to user_id=%s: %s", user_id, exc)


async def _student_teacher_options(db: AsyncSession, student_id: int) -> list[dict]:
    """Return courses and concrete teacher choices available to a student.

    This is used by both the web page and Telegram flow. The important detail is
    that the student must first choose a course and only then a teacher, because a
    student can study several courses and each course can have a different
    teacher. We collect teachers from the student's groups and from schedules for
    the same group/course when schedule-specific teachers exist.
    """
    groups_result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(User.id == student_id)
        .options(
            selectinload(StudyGroup.courses),
            selectinload(StudyGroup.teacher),
        )
        .order_by(StudyGroup.is_active.desc(), StudyGroup.name)
    )
    groups = groups_result.scalars().all()
    group_by_id = {g.id: g for g in groups}
    options: dict[int, dict] = {}

    def ensure_course(course: Course) -> dict:
        return options.setdefault(course.id, {
            "course_id": course.id,
            "course_title": course.title or f"Курс #{course.id}",
            "teachers": [],
            "_seen_teacher_ids": set(),
        })

    def add_teacher(entry: dict, teacher: User | None, group_name: str | None, source: str) -> None:
        if not teacher or not getattr(teacher, "id", None):
            return
        seen = entry.setdefault("_seen_teacher_ids", set())
        if teacher.id in seen:
            return
        seen.add(teacher.id)
        name = (teacher.full_name or teacher.email or "Викладач").strip()
        if teacher.patronymic:
            name = f"{name} {teacher.patronymic}".strip()
        entry["teachers"].append({
            "id": teacher.id,
            "full_name": name,
            "email": teacher.email,
            "group_name": group_name,
            "label": f"{name} ({group_name})" if group_name else name,
            "source": source,
        })

    for group in groups:
        for course in list(group.courses or []):
            entry = ensure_course(course)
            add_teacher(entry, group.teacher, group.name, "group")

    group_ids = list(group_by_id.keys())
    if group_ids:
        schedule_result = await db.execute(
            select(Schedule)
            .where(Schedule.group_id.in_(group_ids))
            .options(selectinload(Schedule.teacher), selectinload(Schedule.discipline))
        )
        for sched in schedule_result.scalars().all():
            discipline = sched.discipline
            course_id = getattr(discipline, "course_id", None) if discipline else None
            if not course_id or course_id not in options:
                continue
            group = group_by_id.get(sched.group_id)
            add_teacher(options[course_id], sched.teacher, group.name if group else None, "schedule")

    result = []
    for entry in options.values():
        entry.pop("_seen_teacher_ids", None)
        entry["teachers"].sort(key=lambda t: (t.get("full_name") or "").lower())
        result.append(entry)
    result.sort(key=lambda x: (x.get("course_title") or "").lower())
    return result


def _course_option(options: list[dict], course_id: int | None) -> Optional[dict]:
    if course_id is None:
        return None
    for item in options:
        if int(item.get("course_id")) == int(course_id):
            return item
    return None


def _teacher_option(course_option: dict | None, teacher_id: int | None) -> Optional[dict]:
    if not course_option or teacher_id is None:
        return None
    for teacher in course_option.get("teachers", []):
        if int(teacher.get("id")) == int(teacher_id):
            return teacher
    return None


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


async def _teacher_can_access_thread(db: AsyncSession, teacher_id: int, thread: QuestionThread) -> bool:
    """Return True when a teacher should see/respond to a thread.

    Primary rule: the thread is directly addressed to this teacher.
    Fallback rule: older/partially-created threads may have target_user_id=NULL;
    in that case, show the thread to teachers who lead the related course.
    The fallback is intentionally NOT used when the thread is addressed to a
    different teacher, so one teacher does not read another teacher's inbox.
    """
    if thread.target_type != "teacher":
        return False
    if thread.target_user_id == teacher_id:
        return True
    if thread.target_user_id is None and thread.course_id is not None:
        return thread.course_id in await get_teacher_course_ids(db, teacher_id)
    return False


async def _assert_can_view(db: AsyncSession, user: User, thread: QuestionThread) -> None:
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.student and thread.student_id == user.id:
        return
    if user.role == UserRole.teacher and await _teacher_can_access_thread(db, user.id, thread):
        return
    raise HTTPException(status_code=403, detail="You do not have access to this question")


async def _assert_can_reply(db: AsyncSession, user: User, thread: QuestionThread) -> None:
    if thread.status == "closed":
        raise HTTPException(status_code=400, detail="Question is closed")
    await _assert_can_view(db, user, thread)
    if thread.target_type == "ai":
        raise HTTPException(status_code=400, detail="AI history cannot be replied to here")


@router.get("/teacher-options")
async def question_teacher_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return course -> teacher choices for the current student.

    The web form and Telegram bot use the same logic: course first, then teacher.
    This prevents the old ambiguous case when a student studied several courses
    and the system silently selected the first available teacher.
    """
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Only students can access teacher options")
    return {"courses": await _student_teacher_options(db, current_user.id)}


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
        options = await _student_teacher_options(db, current_user.id)
        selected_course = _course_option(options, course_id)
        if not selected_course:
            raise HTTPException(status_code=403, detail="Вас не записано на цей курс, тому написати викладачу не можна")
        teachers = selected_course.get("teachers", [])
        if not teachers:
            raise HTTPException(status_code=400, detail="Для цього курсу не призначено викладача — напишіть адміністратору")
        if target_user_id is None:
            if len(teachers) == 1:
                target_user_id = teachers[0]["id"]
            else:
                raise HTTPException(status_code=400, detail="Оберіть конкретного викладача для цього курсу")
        if not _teacher_option(selected_course, target_user_id):
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
        await _send_telegram_message(
            db,
            target_user_id,
            f"Нове питання від студента #{thread.id}: {payload.title.strip()}\n\n{payload.message.strip()}\n\nВідкрийте веб-кабінет → Питання студентів.",
        )
        # Admins also get a light notification, because the admin page is the
        # central oversight place for all appeals, including teacher questions.
        await _notify_admins(db, "Нове питання студент → викладач", payload.title.strip(), "/admin-questions.html")
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
    teacher_course_ids = await get_teacher_course_ids(db, current_user.id)
    stmt = (
        select(QuestionThread)
        .where(QuestionThread.target_type == "teacher")
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
    threads = []
    for thread in result.scalars().all():
        if thread.target_user_id == current_user.id:
            threads.append(thread)
        elif thread.target_user_id is None and thread.course_id in teacher_course_ids:
            threads.append(thread)
    return [_thread_to_response(t) for t in threads]


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

    clean_message = payload.message.strip()

    if current_user.role == UserRole.student:
        thread.status = "waiting_answer"
        if thread.target_type == "teacher":
            await _notify(db, thread.target_user_id, "Студент уточнив питання", thread.title, "/teacher-questions.html")
            await _send_telegram_message(
                db,
                thread.target_user_id,
                f"Студент уточнив питання #{thread.id}: {thread.title}\n\n{clean_message}\n\nВідкрийте веб-кабінет → Питання студентів.",
            )
        elif thread.target_type == "admin":
            await _notify_admins(db, "Студент уточнив звернення", thread.title, "/admin-questions.html")
    else:
        thread.status = "answered"
        await _notify(db, thread.student_id, "Нова відповідь на ваше питання", thread.title, "/questions.html")
        await _send_telegram_message(
            db,
            thread.student_id,
            f"Вам відповіли на звернення #{thread.id}: {thread.title}\n\n{clean_message}\n\nВідповідь також доступна у веб-кабінеті → Питання.",
        )

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
        await _send_telegram_message(
            db,
            thread.student_id,
            f"Ваше звернення #{thread.id} закрито: {thread.title}",
        )
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
        await _send_telegram_message(
            db,
            thread.target_user_id,
            f"Адміністратор передав вам звернення #{thread.id}: {thread.title}\n\nВідкрийте веб-кабінет → Питання студентів.",
        )
    else:
        await _notify_admins(db, "Звернення призначено адміністрації", thread.title, "/admin-questions.html")
    await _notify(db, thread.student_id, "Ваше питання перенаправлено", thread.title, "/questions.html")
    await _send_telegram_message(
        db,
        thread.student_id,
        f"Ваше звернення #{thread.id} перенаправлено: {thread.title}",
    )
    await db.commit()
    return _thread_to_response(await _load_thread(db, thread.id), include_messages=True)
