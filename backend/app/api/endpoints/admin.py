from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from ...database import get_db
from ...models import User, UserRole, Course, StudyGroup, Schedule, Message
from ...schemas import UserResponse, UserCreate, AdminStats, AdminUserRoleUpdate, AdminUserUpdate, UserResponseAdmin, BroadcastRequest
from ...auth import get_current_admin, get_password_hash
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ── List all users ──────────────────────────────────────────────────
@router.get("/users", response_model=List[UserResponseAdmin])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    result = await db.execute(
        select(User).options(selectinload(User.groups))
    )
    return result.scalars().all()


# ── Create user ─────────────────────────────────────────────────────
@router.post("/users", response_model=UserResponseAdmin)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    logger.info("[CREATE USER] email=%s role=%s", user_data.email, user_data.role)
    
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == user_data.email))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    try:
        new_user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            patronymic=user_data.patronymic,
            date_of_birth=user_data.date_of_birth,
            phone=user_data.phone,
            photo_url=user_data.photo_url,
            role=user_data.role,
            password_hash=get_password_hash(user_data.password)
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        logger.info("[CREATE USER] created id=%s", new_user.id)
        return new_user
    except Exception as e:
        logger.warning("[CREATE USER] failed for email=%s", user_data.email)
        raise HTTPException(status_code=400, detail=str(e))


# ── Update user role / block ─────────────────────────────────────────
@router.put("/users/{user_id}", response_model=UserResponseAdmin)
async def update_user(
    user_id: int,
    body: AdminUserUpdate = Body(default_factory=AdminUserUpdate),
    role: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """Update a user from the admin panel.

    This endpoint is intentionally explicit and conservative: older builds accepted
    a loose optional body, which made some frontend saves look successful while the
    changed fields were not applied reliably.  We accept JSON body fields used by
    the admin modal and write only allowed attributes.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Pydantic v2: model_dump; fallback keeps compatibility with v1 if needed.
    if hasattr(body, "model_dump"):
        update_data = body.model_dump(exclude_unset=True)
    else:
        update_data = body.dict(exclude_unset=True)

    if role is not None:
        update_data["role"] = role

    allowed_fields = {"full_name", "email", "patronymic", "date_of_birth", "phone", "photo_url", "role"}
    update_data = {k: v for k, v in update_data.items() if k in allowed_fields}

    # Normalize strings from forms.
    for key in ("full_name", "email", "patronymic", "phone", "photo_url"):
        if key in update_data and isinstance(update_data[key], str):
            update_data[key] = update_data[key].strip()

    if "full_name" in update_data and not update_data["full_name"]:
        raise HTTPException(status_code=400, detail="Full name cannot be empty")
    if "email" in update_data and not update_data["email"]:
        raise HTTPException(status_code=400, detail="Email cannot be empty")

    if user.id == current_admin.id and "role" in update_data:
        raise HTTPException(status_code=400, detail="You cannot change your own role")

    if "email" in update_data:
        existing = await db.execute(
            select(User).where(User.email == update_data["email"], User.id != user_id)
        )
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Email already registered")

    for key, value in update_data.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user


# ── Delete user ─────────────────────────────────────────────────────
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    # Clean up rows that reference this user without an ON DELETE CASCADE,
    # otherwise PostgreSQL raises a ForeignKeyViolation and the delete fails.
    from ...models import Message, Grade, Attendance, Schedule, StudyGroup

    # Messages where the user is the sender or the receiver.
    msgs = await db.execute(
        select(Message).where((Message.sender_id == user_id) | (Message.receiver_id == user_id))
    )
    for m in msgs.scalars().all():
        await db.delete(m)

    # Grades and attendance belonging to the user (as a student).
    grades = await db.execute(select(Grade).where(Grade.student_id == user_id))
    for g in grades.scalars().all():
        await db.delete(g)

    attendance = await db.execute(select(Attendance).where(Attendance.student_id == user_id))
    for a in attendance.scalars().all():
        await db.delete(a)

    # If the user is a teacher, detach them from groups/schedules they led
    # (teacher_id is nullable) so those records survive the deletion.
    led_groups = await db.execute(select(StudyGroup).where(StudyGroup.teacher_id == user_id))
    for grp in led_groups.scalars().all():
        grp.teacher_id = None

    led_schedules = await db.execute(select(Schedule).where(Schedule.teacher_id == user_id))
    for sch in led_schedules.scalars().all():
        sch.teacher_id = None

    await db.flush()
    await db.delete(user)
    await db.commit()
    return {"message": "User deleted"}


# ── System Stats ────────────────────────────────────────────────────
@router.get("/stats", response_model=AdminStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    total_users     = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_students  = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.student))).scalar() or 0
    total_teachers  = (await db.execute(select(func.count(User.id)).where(User.role == UserRole.teacher))).scalar() or 0
    total_courses   = (await db.execute(select(func.count(Course.id)))).scalar() or 0
    total_groups    = (await db.execute(select(func.count(StudyGroup.id)))).scalar() or 0
    active_groups   = (await db.execute(select(func.count(StudyGroup.id)).where(StudyGroup.is_active == True))).scalar() or 0
    total_schedules = (await db.execute(select(func.count(Schedule.id)))).scalar() or 0
    telegram_linked = (await db.execute(select(func.count(User.id)).where(User.telegram_id.isnot(None)))).scalar() or 0

    return AdminStats(
        total_users=total_users,
        total_students=total_students,
        total_teachers=total_teachers,
        total_courses=total_courses,
        total_groups=total_groups,
        active_groups=active_groups,
        total_schedules=total_schedules,
        telegram_linked=telegram_linked
    )


# ── Broadcast notifications ─────────────────────────────────────────
@router.post("/broadcast")
async def broadcast_notification(
    request: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    """
    Send a broadcast message to all linked Telegram users.
    Optionally filter by target_role (student/teacher/admin).
    """
    
    # Build query to fetch users with Telegram linked
    query = select(User).where(User.telegram_id.isnot(None))
    if request.target_role:
        query = query.where(User.role == request.target_role)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    if not users:
        return {"message": "No users found with Telegram linked", "sent_count": 0}
    
    # Send message via bot
    sent_count = 0
    try:
        from ...bot import bot
        if bot:
            for user in users:
                try:
                    await bot.send_message(
                        user.telegram_id,
                        f"*Оголошення від адміністрації:*\n\n{request.message}",
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception as e:
                    logger.warning("[Broadcast] send failed")
    except Exception as e:
        logger.warning("[Broadcast] bot not initialized")
        return {"message": "Bot not initialized", "sent_count": 0}
    
    return {
        "message": f"Broadcast sent successfully",
        "sent_count": sent_count,
        "total_users": len(users)
    }
