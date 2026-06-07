from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from ...auth import get_current_user
from ...database import get_db
from ...models import Notification, User
from ...schemas import NotificationResponse

router = APIRouter()


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(desc(Notification.created_at)).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == current_user.id)
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    item.is_read = True
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/read-all")
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Notification).where(Notification.user_id == current_user.id, Notification.is_read == False))  # noqa: E712
    items = result.scalars().all()
    for item in items:
        item.is_read = True
    await db.commit()
    return {"updated": len(items)}
