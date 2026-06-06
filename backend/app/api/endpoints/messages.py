from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_
from sqlalchemy.orm import selectinload
from typing import List
from ...database import get_db
from ...models import Message, MessageStatus, User, UserRole
from ...schemas import MessageResponse, MessageReply, PublicNotificationCreate, PublicNotificationResponse
from ...auth import get_current_user
from ..access import can_teacher_reply
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Teacher inbox: pending escalated messages ─────────────────────────
@router.get("/inbox", response_model=List[MessageResponse])
async def get_inbox(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or Admin access required")

    query = (
        select(Message)
        .where(Message.is_escalated == True)
        .options(selectinload(Message.sender))
        .order_by(Message.timestamp.desc())
    )
    if current_user.role != UserRole.admin:
        # A teacher should reliably see questions addressed to them, broadcast
        # questions (receiver_id is NULL), AND any question from a student who
        # belongs to one of the groups this teacher leads — even if the bot
        # routed it to a different teacher_id by accident.
        from ...models import StudyGroup, student_group_association

        student_ids_result = await db.execute(
            select(student_group_association.c.student_id)
            .join(StudyGroup, StudyGroup.id == student_group_association.c.group_id)
            .where(StudyGroup.teacher_id == current_user.id)
        )
        my_student_ids = [row[0] for row in student_ids_result.all()]

        conditions = [Message.receiver_id == current_user.id, Message.receiver_id.is_(None)]
        if my_student_ids:
            conditions.append(Message.sender_id.in_(my_student_ids))
        query = query.where(or_(*conditions))

    result = await db.execute(query)
    messages = result.scalars().all()
    return [
        MessageResponse(
            id=m.id,
            sender_id=m.sender_id,
            receiver_id=m.receiver_id,
            sender_name=m.sender.full_name if m.sender else "Невідомий відправник",
            sender_email=m.sender.email if m.sender else "unknown@example.com",
            telegram_id=m.sender.telegram_id if m.sender else None,
            content=m.content,
            reply=m.reply,
            timestamp=m.timestamp,
            status=m.status.value if hasattr(m.status, "value") else str(m.status),
            is_escalated=m.is_escalated,
        )
        for m in messages
    ]


# ── Reply to a pending message ────────────────────────────────────────
@router.post("/reply/{message_id}")
async def reply_to_message(
    message_id: int,
    body: MessageReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or Admin access required")

    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalars().first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    # A teacher may only reply to messages addressed to them or sent by their
    # own students. Admins can reply to anything.
    if current_user.role == UserRole.teacher and not await can_teacher_reply(db, current_user.id, msg):
        raise HTTPException(status_code=403, detail="This message is outside your scope")

    msg.reply  = body.reply
    msg.status = MessageStatus.answered
    await db.commit()

    # Send Telegram notification if student has linked their account
    sender_result = await db.execute(select(User).where(User.id == msg.sender_id))
    sender = sender_result.scalars().first()

    if sender and sender.telegram_id:
        try:
            from ...bot import bot
            if bot:
                await bot.send_message(
                    sender.telegram_id,
                    f"*Відповідь на ваше питання:*\n\n"
                    f"Ваше питання: _{msg.content}_\n\n"
                    f"Відповідь: {body.reply}",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.warning("Telegram notify failed")

    return {"message": "Reply sent", "telegram_notified": bool(sender and sender.telegram_id)}


@router.get("/public", response_model=List[PublicNotificationResponse])
async def get_public_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        select(Message)
        .where(Message.receiver_id.is_(None), Message.is_escalated == False)
        .options(selectinload(Message.sender))
        .order_by(Message.timestamp.desc())
    )
    result = await db.execute(query)
    messages = result.scalars().all()

    from ...models import StudyGroup
    relevant_teacher_ids: set[int] = set()
    is_staff = current_user.role in (UserRole.teacher, UserRole.admin)
    if not is_staff:
        groups_result = await db.execute(
            select(StudyGroup)
            .join(StudyGroup.students)
            .where(User.id == current_user.id)
        )
        for group in groups_result.scalars().all():
            if group.teacher_id is not None:
                relevant_teacher_ids.add(group.teacher_id)

    rows = []
    for message in messages:
        if not is_staff:
            sender = message.sender
            if not (sender is None or sender.role == UserRole.admin or sender.id in relevant_teacher_ids):
                continue
        parts = (message.content or "").split("\n\n", 1)
        title = parts[0].strip() if parts else "Сповіщення"
        body = parts[1].strip() if len(parts) > 1 else (message.reply or "")
        rows.append(
            PublicNotificationResponse(
                id=message.id,
                title=title,
                message=body,
                sender_name=message.sender.full_name if message.sender else None,
                sender_email=message.sender.email if message.sender else None,
                timestamp=message.timestamp,
            )
        )
    return rows


@router.post("/public", response_model=dict)
async def create_public_notification(
    payload: PublicNotificationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or Admin access required")

    content = f"{payload.title}\n\n{payload.message}"
    message = Message(
        sender_id=current_user.id,
        receiver_id=None,
        content=content,
        status=MessageStatus.answered,
        is_escalated=False,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    telegram_sent = 0
    try:
        from ...bot import bot
        if bot:
            if current_user.role == UserRole.teacher:
                # Teacher broadcasts reach only students in the teacher's groups.
                from ...models import StudyGroup
                students_result = await db.execute(
                    select(User)
                    .join(StudyGroup.students)
                    .where(StudyGroup.teacher_id == current_user.id, User.telegram_id.isnot(None))
                )
            else:
                students_result = await db.execute(
                    select(User).where(User.role == UserRole.student, User.telegram_id.isnot(None))
                )
            students = {s.id: s for s in students_result.scalars().all()}.values()
            for student in students:
                try:
                    await bot.send_message(student.telegram_id, f"*{payload.title}*\n\n{payload.message}", parse_mode="Markdown")
                    telegram_sent += 1
                except Exception:
                    continue
    except Exception:
        logger.exception("Failed to broadcast Telegram notification")

    return {"success": True, "notification_id": message.id, "telegram_sent": telegram_sent}
