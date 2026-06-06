from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...auth import get_current_user
from ...database import get_db
from ...models import (
    Assignment,
    AssignmentSubmission,
    Attendance,
    AttendanceStatus,
    Course,
    Discipline,
    Grade,
    Schedule,
    StudyGroup,
    Topic,
    User,
    UserRole,
    student_group_association,
)
from ..access import get_teacher_scope

router = APIRouter()


def _report_payload(report_type: str, title: str, columns: list[str], rows: list[dict], summary: dict):
    return {
        "type": report_type,
        "title": title,
        "generated_at": datetime.utcnow().isoformat(),
        "columns": columns,
        "rows": rows,
        "summary": summary,
    }


@router.get("")
async def get_reports(
    type: str = Query(..., description="attendance|task_completion|teacher_subject_mapping|course_statistics|active_students|graduated_students|excellent_students"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can view reports")

    report_type = type.strip().lower()

    # Teacher reports are scoped to the teacher's own courses/groups/students.
    # scope is None for admins (no restriction).
    scope = await get_teacher_scope(db, current_user)
    teacher_course_ids = set(scope["course_ids"]) if scope is not None else None
    teacher_student_ids = None
    if scope is not None:
        _sid_rows = await db.execute(
            select(student_group_association.c.student_id)
            .join(StudyGroup, StudyGroup.id == student_group_association.c.group_id)
            .where(StudyGroup.teacher_id == current_user.id)
        )
        teacher_student_ids = {r[0] for r in _sid_rows.all()}
    def _course_filter():
        return list(teacher_course_ids) if teacher_course_ids else [-1]
    def _student_filter():
        return list(teacher_student_ids) if teacher_student_ids else [-1]

    if report_type == "attendance":
        _aq = select(Attendance.status)
        if scope is not None:
            _aq = _aq.join(Schedule, Attendance.schedule_id == Schedule.id).where(Schedule.teacher_id == current_user.id)
        rows_result = await db.execute(_aq)
        statuses = rows_result.scalars().all()
        present = sum(1 for s in statuses if s == AttendanceStatus.present)
        late = sum(1 for s in statuses if s == AttendanceStatus.late)
        absent = sum(1 for s in statuses if s == AttendanceStatus.absent)
        total = len(statuses)
        attendance_rate = round((present / total) * 100, 1) if total else 0
        rows = [
            {"metric": "Present", "value": present},
            {"metric": "Late", "value": late},
            {"metric": "Absent", "value": absent},
            {"metric": "Attendance Rate %", "value": attendance_rate},
        ]
        return _report_payload(
            "attendance",
            "Attendance Report",
            ["metric", "value"],
            rows,
            {"records": total},
        )

    if report_type == "task_completion":
        _acount = select(func.count(Assignment.id))
        _scount = select(func.count(AssignmentSubmission.id))
        if scope is not None:
            _acount = _acount.join(Topic, Assignment.topic_id == Topic.id).join(Discipline, Topic.discipline_id == Discipline.id).where(Discipline.course_id.in_(_course_filter()))
            _scount = _scount.join(Assignment, AssignmentSubmission.assignment_id == Assignment.id).join(Topic, Assignment.topic_id == Topic.id).join(Discipline, Topic.discipline_id == Discipline.id).where(Discipline.course_id.in_(_course_filter()))
        assignments_result = await db.execute(_acount)
        submissions_result = await db.execute(_scount)
        assignments_count = assignments_result.scalar() or 0
        submissions_count = submissions_result.scalar() or 0
        completion_rate = round((submissions_count / assignments_count) * 100, 1) if assignments_count else 0
        rows = [
            {"metric": "Assignments", "value": assignments_count},
            {"metric": "Submissions", "value": submissions_count},
            {"metric": "Completion Rate %", "value": completion_rate},
        ]
        return _report_payload(
            "task_completion",
            "Task Completion Report",
            ["metric", "value"],
            rows,
            {"assignments": assignments_count, "submissions": submissions_count},
        )

    if report_type == "teacher_subject_mapping":
        _gq = select(StudyGroup).options(selectinload(StudyGroup.teacher), selectinload(StudyGroup.courses))
        if scope is not None:
            _gq = _gq.where(StudyGroup.teacher_id == current_user.id)
        groups_result = await db.execute(_gq)
        groups = groups_result.scalars().all()
        rows = []
        for group in groups:
            teacher_name = group.teacher.full_name if group.teacher else "Unassigned"
            if not group.courses:
                rows.append({"teacher": teacher_name, "group": group.name, "course": "No course assigned"})
                continue
            for course in group.courses:
                rows.append({"teacher": teacher_name, "group": group.name, "course": course.title})
        return _report_payload(
            "teacher_subject_mapping",
            "Teacher-Subject Mapping",
            ["teacher", "group", "course"],
            rows,
            {"records": len(rows)},
        )

    if report_type == "course_statistics":
        _cq = select(Course)
        if scope is not None:
            _cq = _cq.where(Course.id.in_(_course_filter()))
        courses_result = await db.execute(_cq)
        courses = courses_result.scalars().all()
        rows = []
        for course in courses:
            discipline_count_result = await db.execute(
                select(func.count(Discipline.id)).where(Discipline.course_id == course.id)
            )
            topic_count_result = await db.execute(
                select(func.count(Topic.id))
                .join(Discipline, Topic.discipline_id == Discipline.id)
                .where(Discipline.course_id == course.id)
            )
            assignment_count_result = await db.execute(
                select(func.count(Assignment.id))
                .join(Topic, Assignment.topic_id == Topic.id)
                .join(Discipline, Topic.discipline_id == Discipline.id)
                .where(Discipline.course_id == course.id)
            )
            rows.append(
                {
                    "course": course.title,
                    "disciplines": discipline_count_result.scalar() or 0,
                    "topics": topic_count_result.scalar() or 0,
                    "assignments": assignment_count_result.scalar() or 0,
                }
            )
        return _report_payload(
            "course_statistics",
            "Course Statistics",
            ["course", "disciplines", "topics", "assignments"],
            rows,
            {"courses": len(rows)},
        )

    if report_type == "active_students":
        _stq = select(User).where(User.role == UserRole.student)
        if scope is not None:
            _stq = _stq.where(User.id.in_(_student_filter()))
        students_result = await db.execute(_stq)
        students = students_result.scalars().all()
        rows = []
        for student in students:
            submissions_count_result = await db.execute(
                select(func.count(AssignmentSubmission.id)).where(AssignmentSubmission.student_id == student.id)
            )
            submissions_count = submissions_count_result.scalar() or 0
            if submissions_count > 0:
                rows.append(
                    {
                        "student": student.full_name,
                        "email": student.email,
                        "submissions": submissions_count,
                    }
                )
        return _report_payload(
            "active_students",
            "Active Students",
            ["student", "email", "submissions"],
            rows,
            {"active_students": len(rows)},
        )

    if report_type == "graduated_students":
        _stq = select(User).where(User.role == UserRole.student)
        if scope is not None:
            _stq = _stq.where(User.id.in_(_student_filter()))
        students_result = await db.execute(_stq)
        students = students_result.scalars().all()
        rows = []
        for student in students:
            grade_result = await db.execute(select(Grade.score).where(Grade.student_id == student.id))
            scores = grade_result.scalars().all()
            if not scores:
                continue
            avg_score = sum(scores) / len(scores)
            if avg_score >= 70:
                rows.append(
                    {
                        "student": student.full_name,
                        "email": student.email,
                        "avg_score": round(avg_score, 1),
                        "status": "Graduated",
                    }
                )
        return _report_payload(
            "graduated_students",
            "Graduated Students",
            ["student", "email", "avg_score", "status"],
            rows,
            {"graduated_students": len(rows)},
        )

    if report_type == "excellent_students":
        _stq = select(User).where(User.role == UserRole.student)
        if scope is not None:
            _stq = _stq.where(User.id.in_(_student_filter()))
        students_result = await db.execute(_stq)
        students = students_result.scalars().all()
        rows = []
        for student in students:
            grade_result = await db.execute(select(Grade.score).where(Grade.student_id == student.id))
            scores = grade_result.scalars().all()
            if not scores:
                continue
            avg_score = sum(scores) / len(scores)
            if avg_score >= 90:
                rows.append(
                    {
                        "student": student.full_name,
                        "email": student.email,
                        "avg_score": round(avg_score, 1),
                        "badge": "Excellent",
                    }
                )
        return _report_payload(
            "excellent_students",
            "Excellent Students",
            ["student", "email", "avg_score", "badge"],
            rows,
            {"excellent_students": len(rows)},
        )

    raise HTTPException(
        status_code=400,
        detail="Unsupported report type. Use: attendance, task_completion, teacher_subject_mapping, course_statistics, active_students, graduated_students, excellent_students",
    )
