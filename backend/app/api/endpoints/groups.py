from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from ...database import get_db
from ...models import StudyGroup, UserRole, User, Course
from ...schemas import StudyGroupCreate, StudyGroupResponse
from ...auth import get_current_user, get_current_admin
from ..access import _forbidden

router = APIRouter()


def _serialize_group(group: StudyGroup) -> dict:
    return {
        "id": group.id,
        "name": group.name,
        "teacher_id": group.teacher_id,
        "is_active": group.is_active,
        "course_ids": [course.id for course in group.courses],
        "student_ids": [student.id for student in group.students],
    }

@router.get("/", response_model=List[StudyGroupResponse])
async def get_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(StudyGroup).options(
        selectinload(StudyGroup.courses),
        selectinload(StudyGroup.students),
    )
    if current_user.role == UserRole.teacher:
        query = query.where(StudyGroup.teacher_id == current_user.id)
    elif current_user.role == UserRole.student:
        query = query.join(StudyGroup.students).where(User.id == current_user.id)
    elif current_user.role != UserRole.admin:
        raise _forbidden()
    result = await db.execute(query)
    return [_serialize_group(group) for group in result.scalars().unique().all()]

@router.post("/", response_model=StudyGroupResponse)
async def create_group(
    group: StudyGroupCreate, 
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    payload = group.dict()
    course_ids = set(payload.pop("course_ids", []))
    student_ids = set(payload.pop("student_ids", []))

    if course_ids:
        courses_result = await db.execute(select(Course).where(Course.id.in_(course_ids)))
        courses = courses_result.scalars().all()
        found_ids = {c.id for c in courses}
        missing = sorted(course_ids - found_ids)
        if missing:
            raise HTTPException(status_code=404, detail=f"Courses not found: {missing}")
    else:
        courses = []

    if student_ids:
        students_result = await db.execute(
            select(User)
            .where(User.id.in_(student_ids), User.role == UserRole.student)
            .options(selectinload(User.groups))
        )
        students = students_result.scalars().all()
        found_ids = {student.id for student in students}
        missing = sorted(student_ids - found_ids)
        if missing:
            raise HTTPException(status_code=404, detail=f"Students not found: {missing}")
    else:
        students = []

    for student in students:
        active_groups_count = sum(1 for existing_group in student.groups if existing_group.is_active)
        if active_groups_count >= 2 and payload.get("is_active", True):
            raise HTTPException(
                status_code=400,
                detail=f"Student {student.full_name} already has 2 active groups",
            )

    db_group = StudyGroup(**payload)
    db_group.courses = courses
    db_group.students = students
    db.add(db_group)
    await db.commit()
    await db.refresh(db_group)
    await db.refresh(db_group, ["courses", "students"])
    return _serialize_group(db_group)

@router.post("/{group_id}/enroll/{student_id}")
async def enroll_student(
    group_id: int,
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    # Check if student exists
    result = await db.execute(
        select(User)
        .where(User.id == student_id, User.role == UserRole.student)
        .options(selectinload(User.groups))
    )
    student = result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Check if group exists
    result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.id == group_id)
        .options(selectinload(StudyGroup.students), selectinload(StudyGroup.courses))
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if student is already in the group
    if student in group.students:
        raise HTTPException(status_code=400, detail="Student already enrolled in this group")

    # Business rule: max 2 active groups (group-level, not course-level)
    active_groups_count = sum(1 for g in student.groups if g.is_active)
    if active_groups_count >= 2 and group.is_active:
        raise HTTPException(status_code=400, detail="Student already has 2 active groups")
    
    group.students.append(student)
    await db.commit()
    await db.refresh(group, ["courses", "students"])
    return {"message": f"Student {student.full_name} enrolled in group {group.name}"}


@router.post("/{group_id}/courses/{course_id}")
async def add_course_to_group(
    group_id: int,
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    group_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.id == group_id)
        .options(selectinload(StudyGroup.courses))
    )
    group = group_result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    # Check if course is already in group's pool (m2m)
    if course not in group.courses:
        group.courses.append(course)

    await db.commit()
    await db.refresh(group, ["courses"])
    
    course_ids = [c.id for c in group.courses]
    return {
        "message": f"Course {course_id} added to group {group.name}",
        "group_id": group.id,
        "course_ids": course_ids,
    }


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    group = (await db.execute(select(StudyGroup).where(StudyGroup.id == group_id))).scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await db.delete(group)
    await db.commit()
    return {"message": "Group deleted"}


@router.delete("/{group_id}/enroll/{student_id}")
async def unenroll_student(
    group_id: int,
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    """Remove a student from a group."""
    result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.id == group_id)
        .options(selectinload(StudyGroup.students), selectinload(StudyGroup.courses))
    )
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    student = next((s for s in group.students if s.id == student_id), None)
    if not student:
        raise HTTPException(status_code=404, detail="Student is not in this group")

    group.students.remove(student)
    await db.commit()
    await db.refresh(group, ["courses", "students"])
    return {"message": f"Student removed from group {group.name}"}
