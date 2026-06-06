from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
import datetime
from ...database import get_db
from ...models import Schedule, User, UserRole, student_group_association
from ...schemas import ScheduleCreate, ScheduleResponse
from ...auth import get_current_admin, get_current_user

router = APIRouter()


def _combine_dt(date_value: datetime.date, time_value: datetime.time) -> datetime.datetime:
    return datetime.datetime.combine(date_value, time_value)


def _default_end_time(start_time: datetime.time) -> datetime.time:
    return (_combine_dt(datetime.date.today(), start_time) + datetime.timedelta(minutes=90)).time()


async def validate_schedule_payload(db: AsyncSession, payload: ScheduleCreate) -> None:
    """Ensure referenced entities exist and are consistent before saving a lesson:
    teacher_id is a real teacher, group/discipline exist, and the discipline's
    course is actually assigned to the group."""
    from ...models import StudyGroup, Discipline, Course  # local import to avoid cycles

    teacher = (await db.execute(select(User).where(User.id == payload.teacher_id))).scalar_one_or_none()
    if not teacher or teacher.role != UserRole.teacher:
        raise HTTPException(status_code=400, detail="teacher_id must belong to a teacher")

    group = (await db.execute(
        select(StudyGroup).where(StudyGroup.id == payload.group_id).options(selectinload(StudyGroup.courses))
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    discipline = (await db.execute(
        select(Discipline).where(Discipline.id == payload.discipline_id)
    )).scalar_one_or_none()
    if not discipline:
        raise HTTPException(status_code=404, detail="Discipline not found")

    if discipline.course_id not in {c.id for c in group.courses}:
        raise HTTPException(status_code=400, detail="Discipline's course is not assigned to this group")


def _overlaps(
    start_a: datetime.datetime,
    end_a: datetime.datetime,
    start_b: datetime.datetime,
    end_b: datetime.datetime,
) -> bool:
    return start_a < end_b and start_b < end_a

@router.get("/", response_model=List[ScheduleResponse])
async def get_schedule(
    date: Optional[datetime.date] = Query(None),
    group_id: Optional[int] = Query(None),
    teacher_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Schedule).options(
        selectinload(Schedule.discipline),
        selectinload(Schedule.group),
        selectinload(Schedule.teacher),
    )
    if date:
        query = query.where(Schedule.date == date)
    if group_id:
        query = query.where(Schedule.group_id == group_id)
    if teacher_id:
        query = query.where(Schedule.teacher_id == teacher_id)

    # Role-based scoping: a student sees only the schedule of their own groups;
    # a teacher sees only the lessons they teach; an admin sees everything.
    if current_user.role == UserRole.student:
        gid_result = await db.execute(
            select(student_group_association.c.group_id)
            .where(student_group_association.c.student_id == current_user.id)
        )
        group_ids = [row[0] for row in gid_result.all()]
        if not group_ids:
            return []
        query = query.where(Schedule.group_id.in_(group_ids))
    elif current_user.role == UserRole.teacher:
        query = query.where(Schedule.teacher_id == current_user.id)

    result = await db.execute(query)
    schedules = result.scalars().all()
    return [
        ScheduleResponse(
            id=s.id,
            date=s.date,
            time=s.time,
            end_time=s.end_time,
            group_id=s.group_id,
            teacher_id=s.teacher_id,
            discipline_id=s.discipline_id,
            meeting_link=s.meeting_link,
            discipline_name=s.discipline.name if s.discipline else None,
            group_name=s.group.name if s.group else None,
            teacher_name=s.teacher.full_name if s.teacher else None,
        )
        for s in schedules
    ]

@router.post("/", response_model=ScheduleResponse)
async def create_schedule(
    schedule: ScheduleCreate, 
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    await validate_schedule_payload(db, schedule)
    requested_end_time = schedule.end_time or _default_end_time(schedule.time)
    requested_start_dt = _combine_dt(schedule.date, schedule.time)
    requested_end_dt = _combine_dt(schedule.date, requested_end_time)

    if requested_end_dt <= requested_start_dt:
        raise HTTPException(status_code=400, detail="end_time must be later than time")

    existing_result = await db.execute(
        select(Schedule)
        .where(
            Schedule.date == schedule.date,
            (Schedule.group_id == schedule.group_id) | (Schedule.teacher_id == schedule.teacher_id),
        )
        .options(
            selectinload(Schedule.discipline),
            selectinload(Schedule.group),
            selectinload(Schedule.teacher),
        )
    )
    existing_schedules = existing_result.scalars().all()

    for existing in existing_schedules:
        existing_end_time = existing.end_time or _default_end_time(existing.time)
        existing_start_dt = _combine_dt(existing.date, existing.time)
        existing_end_dt = _combine_dt(existing.date, existing_end_time)

        if _overlaps(requested_start_dt, requested_end_dt, existing_start_dt, existing_end_dt):
            conflict_parts = []
            if existing.group_id == schedule.group_id:
                conflict_parts.append("same group")
            if existing.teacher_id == schedule.teacher_id:
                conflict_parts.append("same teacher")

            discipline_name = existing.discipline.name if existing.discipline else f"discipline_id={existing.discipline_id}"
            group_name = existing.group.name if existing.group else f"group_id={existing.group_id}"
            teacher_name = existing.teacher.full_name if existing.teacher else f"teacher_id={existing.teacher_id}"
            reasons = ", ".join(conflict_parts) if conflict_parts else "time overlap"

            detail = (
                f"Schedule overlap ({reasons}) with '{discipline_name}' for group '{group_name}' "
                f"by teacher '{teacher_name}' on {existing.date.isoformat()} "
                f"{existing.time.strftime('%H:%M')}-{existing_end_time.strftime('%H:%M')}"
            )
            raise HTTPException(status_code=400, detail=detail)

    db_schedule = Schedule(**schedule.dict())
    if db_schedule.end_time is None:
        db_schedule.end_time = requested_end_time
    db.add(db_schedule)
    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    schedule_result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    db_schedule = schedule_result.scalars().first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await validate_schedule_payload(db, schedule)

    requested_end_time = schedule.end_time or _default_end_time(schedule.time)
    requested_start_dt = _combine_dt(schedule.date, schedule.time)
    requested_end_dt = _combine_dt(schedule.date, requested_end_time)

    if requested_end_dt <= requested_start_dt:
        raise HTTPException(status_code=400, detail="end_time must be later than time")

    existing_result = await db.execute(
        select(Schedule)
        .where(
            Schedule.id != schedule_id,
            Schedule.date == schedule.date,
            (Schedule.group_id == schedule.group_id) | (Schedule.teacher_id == schedule.teacher_id),
        )
        .options(
            selectinload(Schedule.discipline),
            selectinload(Schedule.group),
            selectinload(Schedule.teacher),
        )
    )
    existing_schedules = existing_result.scalars().all()

    for existing in existing_schedules:
        existing_end_time = existing.end_time or _default_end_time(existing.time)
        existing_start_dt = _combine_dt(existing.date, existing.time)
        existing_end_dt = _combine_dt(existing.date, existing_end_time)

        if _overlaps(requested_start_dt, requested_end_dt, existing_start_dt, existing_end_dt):
            conflict_parts = []
            if existing.group_id == schedule.group_id:
                conflict_parts.append("same group")
            if existing.teacher_id == schedule.teacher_id:
                conflict_parts.append("same teacher")

            discipline_name = existing.discipline.name if existing.discipline else f"discipline_id={existing.discipline_id}"
            group_name = existing.group.name if existing.group else f"group_id={existing.group_id}"
            teacher_name = existing.teacher.full_name if existing.teacher else f"teacher_id={existing.teacher_id}"
            reasons = ", ".join(conflict_parts) if conflict_parts else "time overlap"

            detail = (
                f"Schedule overlap ({reasons}) with '{discipline_name}' for group '{group_name}' "
                f"by teacher '{teacher_name}' on {existing.date.isoformat()} "
                f"{existing.time.strftime('%H:%M')}-{existing_end_time.strftime('%H:%M')}"
            )
            raise HTTPException(status_code=400, detail=detail)

    db_schedule.date = schedule.date
    db_schedule.time = schedule.time
    db_schedule.end_time = requested_end_time
    db_schedule.group_id = schedule.group_id
    db_schedule.teacher_id = schedule.teacher_id
    db_schedule.discipline_id = schedule.discipline_id
    db_schedule.meeting_link = schedule.meeting_link

    await db.commit()
    await db.refresh(db_schedule)
    return db_schedule


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Delete a scheduled lesson (admin only)."""
    result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
    db_schedule = result.scalars().first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Remove dependent attendance records first to avoid FK violations.
    from ...models import Attendance
    attendance_rows = await db.execute(
        select(Attendance).where(Attendance.schedule_id == schedule_id)
    )
    for record in attendance_rows.scalars().all():
        await db.delete(record)

    await db.delete(db_schedule)
    await db.commit()
    return {"message": "Schedule deleted"}
