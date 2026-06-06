from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from ...database import get_db
from ...models import Discipline, Course, User, UserRole
from ...auth import get_current_user
from ..access import require_teacher_course_access

router = APIRouter()


@router.get("/")
async def get_disciplines(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return full disciplines directory with course context."""
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can view disciplines")

    result = await db.execute(
        select(Discipline, Course.title)
        .join(Course, Discipline.course_id == Course.id)
        .order_by(Course.title, Discipline.name)
    )
    rows = result.all()

    return [
        {
            "id": discipline.id,
            "name": discipline.name,
            "course_id": discipline.course_id,
            "course_title": course_title,
        }
        for discipline, course_title in rows
    ]


from pydantic import BaseModel


class DisciplineCreate(BaseModel):
    name: str
    course_id: int


@router.post("/")
async def create_discipline(
    payload: DisciplineCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can create disciplines")
    await require_teacher_course_access(db, current_user, payload.course_id)
    if not (payload.name or "").strip():
        raise HTTPException(status_code=400, detail="Discipline name is required")
    course = (await db.execute(select(Course).where(Course.id == payload.course_id))).scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    discipline = Discipline(name=payload.name.strip(), course_id=payload.course_id)
    db.add(discipline)
    await db.commit()
    await db.refresh(discipline)
    return {"id": discipline.id, "name": discipline.name, "course_id": discipline.course_id, "course_title": course.title}


@router.delete("/{discipline_id}")
async def delete_discipline(
    discipline_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can delete disciplines")
    discipline = (await db.execute(select(Discipline).where(Discipline.id == discipline_id))).scalars().first()
    if not discipline:
        raise HTTPException(status_code=404, detail="Discipline not found")
    await require_teacher_course_access(db, current_user, discipline.course_id)
    await db.delete(discipline)
    await db.commit()
    return {"message": "Discipline deleted"}
