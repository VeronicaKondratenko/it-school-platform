from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from ...database import get_db
from ...models import User, StudyGroup, TelegramLinkCode
from ...schemas import UserResponse, UserUpdate
from ...auth import get_current_user
import hashlib
import secrets
import datetime

router = APIRouter()


def hash_link_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()

@router.get("/me", response_model=UserResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(selectinload(User.groups).selectinload(StudyGroup.courses))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    update_data = user_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)
    
    await db.commit()
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(selectinload(User.groups).selectinload(StudyGroup.courses))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/me/telegram-link-code")
async def create_telegram_link_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a one-time code (valid 10 minutes) to link a Telegram account.

    The user enters this code in the bot via `/link CODE`. Only the SHA-256 hash
    is stored server-side.
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

    # Invalidate any previous unused codes for this user.
    old = await db.execute(
        select(TelegramLinkCode).where(
            TelegramLinkCode.user_id == current_user.id,
            TelegramLinkCode.used_at.is_(None),
        )
    )
    for row in old.scalars().all():
        row.used_at = datetime.datetime.utcnow()

    db.add(TelegramLinkCode(
        user_id=current_user.id,
        code_hash=hash_link_code(code),
        expires_at=expires_at,
    ))
    await db.commit()
    return {"code": code, "expires_in_minutes": 10}
