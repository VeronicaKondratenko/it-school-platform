"""Centralised access-control (RBAC + ownership) helpers.

These functions are the single source of truth for "who is allowed to touch what".
Endpoints import and call them instead of re-implementing role/ownership checks,
which keeps the rules consistent and easy to audit.

Conventions:
  * admin  → full access everywhere.
  * teacher → access scoped to courses/groups they lead (StudyGroup.teacher_id).
  * student → access scoped to courses/groups they belong to.
"""
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from ..models import (
    User,
    UserRole,
    StudyGroup,
    Course,
    Assignment,
    Topic,
    Discipline,
    Schedule,
    Message,
    student_group_association,
)


def _forbidden(detail: str = "Access denied") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _not_found(detail: str = "Not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


async def get_student_course_ids(db: AsyncSession, student_id: int) -> set[int]:
    """All course ids the student can access through active groups."""
    result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(User.id == student_id, StudyGroup.is_active == True)  # noqa: E712
        .options(selectinload(StudyGroup.courses))
    )
    return {c.id for g in result.scalars().all() for c in g.courses}


async def get_teacher_course_ids(db: AsyncSession, teacher_id: int) -> set[int]:
    """All course ids the teacher leads through their groups."""
    result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.teacher_id == teacher_id)
        .options(selectinload(StudyGroup.courses))
    )
    return {c.id for g in result.scalars().all() for c in g.courses}


async def get_student_group_ids(db: AsyncSession, student_id: int) -> set[int]:
    result = await db.execute(
        select(student_group_association.c.group_id)
        .where(student_group_association.c.student_id == student_id)
    )
    return {row[0] for row in result.all()}


async def require_course_read_access(db: AsyncSession, user: User, course_id: int) -> None:
    """Anyone enrolled (student), leading (teacher), or admin may read a course."""
    if user.role == UserRole.admin:
        return
    if user.role == UserRole.teacher:
        if course_id in await get_teacher_course_ids(db, user.id):
            return
        raise _forbidden("You do not teach this course")
    if user.role == UserRole.student:
        if course_id in await get_student_course_ids(db, user.id):
            return
        raise _forbidden("You are not enrolled in this course")
    raise _forbidden()


async def require_teacher_course_access(db: AsyncSession, user: User, course_id: int) -> None:
    """Write access to a course's content (topics/materials/disciplines)."""
    if user.role == UserRole.admin:
        return
    if user.role != UserRole.teacher:
        raise _forbidden("Teacher or admin access required")
    result = await db.execute(
        select(StudyGroup.id).where(
            StudyGroup.teacher_id == user.id,
            StudyGroup.courses.any(Course.id == course_id),
        )
    )
    if result.scalar_one_or_none() is None:
        raise _forbidden("You do not teach this course")


def _assignment_course_id(assignment: Assignment):
    topic = getattr(assignment, "topic", None)
    discipline = getattr(topic, "discipline", None) if topic else None
    return getattr(discipline, "course_id", None) if discipline else None


async def load_assignment_with_course(db: AsyncSession, assignment_id: int) -> Assignment:
    result = await db.execute(
        select(Assignment)
        .where(Assignment.id == assignment_id)
        .options(selectinload(Assignment.topic).selectinload(Topic.discipline))
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise _not_found("Assignment not found")
    return assignment


async def require_student_can_access_assignment(db: AsyncSession, student_id: int, assignment: Assignment) -> None:
    course_id = _assignment_course_id(assignment)
    if course_id is None or course_id not in await get_student_course_ids(db, student_id):
        raise _forbidden("Assignment is not available for this student")


async def require_schedule_access(db: AsyncSession, schedule_id: int, user: User, *, write: bool = False) -> Schedule:
    result = await db.execute(
        select(Schedule).where(Schedule.id == schedule_id).options(selectinload(Schedule.group))
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise _not_found("Schedule not found")
    if user.role == UserRole.admin:
        return schedule
    if user.role == UserRole.teacher:
        if schedule.teacher_id == user.id:
            return schedule
        group = schedule.group
        if group is not None and group.teacher_id == user.id:
            return schedule
        raise _forbidden("This schedule does not belong to this teacher")
    if user.role == UserRole.student:
        if write:
            # students may only mark their own attendance, not edit the schedule itself
            pass
        if schedule.group_id in await get_student_group_ids(db, user.id):
            return schedule
        raise _forbidden("This lesson is not in your group")
    raise _forbidden()


async def can_teacher_reply(db: AsyncSession, teacher_id: int, msg: Message) -> bool:
    if msg.receiver_id == teacher_id:
        return True
    result = await db.execute(
        select(student_group_association.c.student_id)
        .join(StudyGroup, StudyGroup.id == student_group_association.c.group_id)
        .where(
            StudyGroup.teacher_id == teacher_id,
            student_group_association.c.student_id == msg.sender_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_teacher_scope(db: AsyncSession, user: User):
    """Return {group_ids, course_ids} for a teacher, or None for admin (no limit)."""
    if user.role == UserRole.admin:
        return None
    groups = (await db.execute(
        select(StudyGroup)
        .where(StudyGroup.teacher_id == user.id)
        .options(selectinload(StudyGroup.courses))
    )).scalars().all()
    return {
        "group_ids": [g.id for g in groups],
        "course_ids": list({c.id for g in groups for c in g.courses}),
    }
