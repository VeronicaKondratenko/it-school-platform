from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from ...database import get_db
from ...models import Attendance, Schedule, User, UserRole, AttendanceStatus, StudyGroup
from ...auth import get_current_user
from ...schemas import AttendanceUpdate, AttendanceResponse
from ..access import require_schedule_access
from pydantic import BaseModel

# Schema for teacher roster view
class StudentAttendanceInfo(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    status: Optional[str]  # "present", "late", "absent", or None if not marked
    
    class Config:
        from_attributes = True

router = APIRouter()

@router.post("/{schedule_id}")
async def mark_attendance(
    schedule_id: int,
    attendance: AttendanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Student self-marks attendance for a schedule item"""
    
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="Only students can self-mark attendance")
    
    # Student may only mark attendance for lessons of their own group.
    await require_schedule_access(db, schedule_id, current_user, write=True)
    
    # Check if attendance record exists
    attendance_result = await db.execute(
        select(Attendance).where(
            Attendance.schedule_id == schedule_id,
            Attendance.student_id == current_user.id
        )
    )
    attendance_record = attendance_result.scalars().first()
    
    # Validate status
    try:
        status_enum = AttendanceStatus(attendance.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {[s.value for s in AttendanceStatus]}")
    
    if attendance_record:
        attendance_record.status = status_enum
    else:
        attendance_record = Attendance(
            student_id=current_user.id,
            schedule_id=schedule_id,
            status=status_enum
        )
        db.add(attendance_record)
    
    await db.commit()
    return {"success": True, "status": status_enum.value}

@router.get("/{schedule_id}")
async def get_attendance(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get attendance status for a student on a schedule item"""
    
    await require_schedule_access(db, schedule_id, current_user)
    attendance_result = await db.execute(
        select(Attendance).where(
            Attendance.schedule_id == schedule_id,
            Attendance.student_id == current_user.id
        )
    )
    attendance_record = attendance_result.scalars().first()
    
    return {
        "status": attendance_record.status.value if attendance_record else AttendanceStatus.absent.value,
        "schedule_id": schedule_id,
        "student_id": current_user.id
    }

# ── TEACHER/ADMIN: Manual attendance marking for any student ──────────────────
@router.post("/teacher/mark/{schedule_id}/{student_id}", response_model=AttendanceResponse)
async def teacher_mark_attendance(
    schedule_id: int,
    student_id: int,
    body: AttendanceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Teacher/Admin manually marks attendance for a specific student.
    Allowed only for teacher/admin. Any teacher can mark attendance for any schedule.
    """
    
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Only teacher or admin can manually mark attendance")
    
    # Teacher may only mark attendance for their own schedules; admin: any.
    schedule = await require_schedule_access(db, schedule_id, current_user, write=True)
    
    # Verify student exists
    student_result = await db.execute(
        select(User).where(User.id == student_id, User.role == UserRole.student)
    )
    if not student_result.scalars().first():
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Student must belong to this lesson's group (no marking outsiders).
    group_result = await db.execute(
        select(StudyGroup).where(StudyGroup.id == schedule.group_id).options(selectinload(StudyGroup.students))
    )
    group = group_result.scalars().first()
    if not group or student_id not in {s.id for s in group.students}:
        raise HTTPException(status_code=403, detail="Student is not in this schedule group")
    
    # Validate status
    try:
        status_enum = AttendanceStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {[s.value for s in AttendanceStatus]}")
    
    # Create or update attendance record
    attendance_result = await db.execute(
        select(Attendance).where(
            Attendance.schedule_id == schedule_id,
            Attendance.student_id == student_id
        )
    )
    attendance_record = attendance_result.scalars().first()
    
    if attendance_record:
        attendance_record.status = status_enum
    else:
        attendance_record = Attendance(
            student_id=student_id,
            schedule_id=schedule_id,
            status=status_enum
        )
        db.add(attendance_record)
    
    await db.commit()
    await db.refresh(attendance_record)
    return attendance_record

# ── Get all attendance records for a schedule (for teacher view) ──────────────────
@router.get("/schedule/{schedule_id}/all", response_model=List[AttendanceResponse])
async def get_schedule_attendance(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all attendance records for a specific schedule.
    Any teacher/admin can view records for any schedule.
    """
    
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or Admin access required")
    
    await require_schedule_access(db, schedule_id, current_user)
    
    attendance_result = await db.execute(
        select(Attendance).where(Attendance.schedule_id == schedule_id)
    )
    records = attendance_result.scalars().all()
    return records

# ── Get class roster with attendance status for teacher ──────────────────
@router.get("/teacher/roster/{schedule_id}", response_model=List[StudentAttendanceInfo])
async def get_class_roster(
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all students in the group for a specific schedule with their attendance status.
    Any teacher or admin can see any schedule roster (not restricted to own schedules).
    """
    
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or Admin access required")
    
    # Teacher may only view rosters of their own schedules; admin: any.
    schedule = await require_schedule_access(db, schedule_id, current_user)
    
    # Get the study group
    group_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.id == schedule.group_id)
        .options(selectinload(StudyGroup.students))
    )
    group = group_result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Study group not found")
    
    # Get all attendance records for this schedule
    attendance_result = await db.execute(
        select(Attendance).where(Attendance.schedule_id == schedule_id)
    )
    attendance_records = attendance_result.scalars().all()
    attendance_map = {a.student_id: a.status.value for a in attendance_records}
    
    # Build response with all students in group
    roster = []
    for student in group.students:
        roster.append(StudentAttendanceInfo(
            student_id=student.id,
            student_name=student.full_name,
            student_email=student.email,
            status=attendance_map.get(student.id, None)
        ))
    
    # Sort by name for consistency
    roster.sort(key=lambda x: x.student_name)
    return roster
