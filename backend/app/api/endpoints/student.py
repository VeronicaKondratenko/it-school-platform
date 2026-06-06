"""
Student-facing API endpoints:
  GET /api/student/assignments   – assignments from the student's active groups
  GET /api/student/grades        – graded assignments for the student
  GET /api/student/courses       – student's enrolled courses with grades grouped by course
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, func
from sqlalchemy.orm import selectinload
from typing import List
import datetime

from ...database import get_db
from ...models import User, Grade, Assignment, Topic, Discipline, Course, StudyGroup, AssignmentSubmission, UserRole, Message
from ...schemas import GradeResponse, StudentCourseWithGradesResponse, AssignmentWithCourseResponse, AssignmentSubmissionCreate, PublicNotificationResponse
from ...auth import get_current_user

router = APIRouter()
@router.get("/notifications", response_model=List[PublicNotificationResponse])
async def get_student_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Message)
        .where(Message.receiver_id.is_(None), Message.is_escalated == False)
        .options(selectinload(Message.sender))
        .order_by(Message.timestamp.desc())
    )
    messages = result.scalars().all()

    # Determine which teachers are relevant to this user.
    # A student should only see course-specific announcements written by the
    # teacher(s) of the group(s) they belong to — plus global announcements
    # written by an administrator (system-wide notices like maintenance/welcome).
    # Teachers and admins see everything.
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

    def _is_visible(message: Message) -> bool:
        if is_staff:
            return True
        sender = message.sender
        # Global announcement: no sender or authored by an administrator.
        if sender is None or sender.role == UserRole.admin:
            return True
        # Course-specific announcement: only if authored by one of the
        # student's own teachers.
        return sender.id in relevant_teacher_ids

    notifications = []
    for message in messages:
        if not _is_visible(message):
            continue
        parts = (message.content or "").split("\n\n", 1)
        notifications.append(
            PublicNotificationResponse(
                id=message.id,
                title=parts[0].strip() if parts else "Сповіщення",
                message=parts[1].strip() if len(parts) > 1 else "",
                sender_name=message.sender.full_name if message.sender else None,
                sender_email=message.sender.email if message.sender else None,
                timestamp=message.timestamp,
            )
        )
    return notifications



def _collect_course_ids(groups: List[StudyGroup]) -> set[int]:
    course_ids = set()
    for group in groups:
        course_ids.update(c.id for c in group.courses)
    return course_ids


@router.get("/assignments", response_model=List[AssignmentWithCourseResponse])
async def get_student_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all assignments whose topics belong to disciplines that are
    part of courses that the current student is enrolled in.
    Includes course and discipline information.
    """
    # Get student's groups
    result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(User.id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = result.scalars().all()

    if not groups:
        return []

    course_ids = list(_collect_course_ids(groups))
    if not course_ids:
        return []

    # Get topics within those courses with eager loading
    result = await db.execute(
        select(Topic)
        .join(Discipline, Topic.discipline_id == Discipline.id)
        .where(Discipline.course_id.in_(course_ids))
        .options(selectinload(Topic.discipline))
    )
    topics = result.scalars().all()
    if not topics:
        return []

    topic_ids = [t.id for t in topics]

    # Get assignments for those topics with eager loading
    result = await db.execute(
        select(Assignment)
        .where(Assignment.topic_id.in_(topic_ids))
        .options(selectinload(Assignment.topic).selectinload(Topic.discipline))
        .order_by(Assignment.id)
    )
    assignments = result.scalars().all()

    # Fetch graded assignments for current student to compute status.
    graded_result = await db.execute(
        select(Grade.assignment_id).where(Grade.student_id == current_user.id)
    )
    graded_assignment_ids = set(graded_result.scalars().all())

    assignment_ids = [a.id for a in assignments]
    submissions_result = await db.execute(
        select(AssignmentSubmission.assignment_id).where(
            AssignmentSubmission.student_id == current_user.id,
            AssignmentSubmission.assignment_id.in_(assignment_ids),
        )
    )
    submitted_assignment_ids = set(submissions_result.scalars().all())
    today = datetime.date.today()
    
    # Enrich assignments with course and discipline info
    response_list = []
    for assignment in assignments:
        discipline_name = assignment.topic.discipline.name if assignment.topic and assignment.topic.discipline else "Unknown"
        course_id = assignment.topic.discipline.course_id if assignment.topic and assignment.topic.discipline else None

        if assignment.id in graded_assignment_ids:
            status = "graded"
        elif assignment.id in submitted_assignment_ids:
            status = "submitted"
        elif assignment.due_date and assignment.due_date < today:
            status = "overdue"
        else:
            status = "pending"

        if not assignment.due_date:
            priority = "medium"
        else:
            days_left = (assignment.due_date - today).days
            if days_left <= 3:
                priority = "high"
            elif days_left <= 7:
                priority = "medium"
            else:
                priority = "low"
        
        response_list.append(
            AssignmentWithCourseResponse(
                id=assignment.id,
                title=assignment.title,
                description=assignment.description,
                due_date=assignment.due_date,
                topic_id=assignment.topic_id,
                discipline_name=discipline_name,
                course_id=course_id,
                status=status,
                priority=priority,
            )
        )
    
    return response_list


@router.post("/assignments/{assignment_id}/submit")
async def submit_student_assignment(
    assignment_id: int,
    payload: AssignmentSubmissionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit (or resubmit) an assignment for the current student.
    The assignment must belong to one of the student's enrolled courses.
    """
    assignment_result = await db.execute(
        select(Assignment)
        .where(Assignment.id == assignment_id)
        .options(selectinload(Assignment.topic).selectinload(Topic.discipline))
    )
    assignment = assignment_result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    groups_result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(User.id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = groups_result.scalars().all()
    course_ids = _collect_course_ids(groups)

    assignment_course_id = (
        assignment.topic.discipline.course_id
        if assignment.topic and assignment.topic.discipline
        else None
    )
    if assignment_course_id not in course_ids:
        raise HTTPException(status_code=403, detail="Assignment is not available for this student")

    graded_result = await db.execute(
        select(Grade.id).where(
            Grade.student_id == current_user.id,
            Grade.assignment_id == assignment_id,
        )
    )
    if graded_result.scalars().first() is not None:
        raise HTTPException(status_code=400, detail="Assignment is already graded")

    submission_result = await db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.student_id == current_user.id,
            AssignmentSubmission.assignment_id == assignment_id,
        )
    )
    submission = submission_result.scalars().first()

    if submission:
        if submission.is_locked:
            raise HTTPException(status_code=400, detail="Submission is locked. Ask teacher to reset")
        submission.content = payload.content
        submission.file_name = payload.file_name
        submission.is_locked = True
        submission.submitted_at = datetime.datetime.utcnow()
    else:
        submission = AssignmentSubmission(
            student_id=current_user.id,
            assignment_id=assignment_id,
            content=payload.content,
            file_name=payload.file_name,
            is_locked=True,
        )
        db.add(submission)

    await db.commit()

    return {
        "message": "Assignment submitted",
        "assignment_id": assignment_id,
        "status": "submitted",
    }


@router.get("/grades", response_model=List[GradeResponse])
async def get_student_grades(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all Grade records belonging to the current student,
    with the assignment details eagerly loaded.
    """
    result = await db.execute(
        select(Grade)
        .where(Grade.student_id == current_user.id)
        .options(selectinload(Grade.assignment))
        .order_by(Grade.graded_at.desc())
    )
    return result.scalars().all()


@router.get("/courses", response_model=List[StudentCourseWithGradesResponse])
async def get_student_courses_with_grades(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns list of courses where student is enrolled with their grades per course.
    Grades are grouped by course. Includes count of enrolled students per course.
    """
    # Get student's study groups
    result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(User.id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = result.scalars().all()

    if not groups:
        return []

    course_ids = _collect_course_ids(groups)
    if not course_ids:
        return []

    courses_result = await db.execute(select(Course).where(Course.id.in_(course_ids)))
    courses = courses_result.scalars().all()
    courses_dict = {course.id: course for course in courses}

    # For each course, get student's grades for assignments in that course
    result_list = []
    for course_id, course in courses_dict.items():
        # Get all study groups that have this course
        course_groups_result = await db.execute(
            select(StudyGroup)
            .where(StudyGroup.courses.any(Course.id == course_id))
        )
        course_groups = course_groups_result.scalars().all()
        
        # Count unique students in those groups
        enrolled_students_count = 0
        if course_groups:
            group_ids = [g.id for g in course_groups]
            students_count_result = await db.execute(
                select(func.count(func.distinct(User.id)))
                .join(StudyGroup.students)
                .where(StudyGroup.id.in_(group_ids), User.role == UserRole.student)
            )
            enrolled_students_count = students_count_result.scalar() or 0

        # Get all topics for this course
        topics_result = await db.execute(
            select(Topic)
            .join(Discipline, Topic.discipline_id == Discipline.id)
            .where(Discipline.course_id == course_id)
        )
        topics = topics_result.scalars().all()

        if not topics:
            # No assignments in this course
            result_list.append(
                StudentCourseWithGradesResponse(
                    course_id=course_id,
                    course_title=course.title,
                    grades=[],
                    average_score=None,
                    grades_count=0,
                    enrolled_students_count=enrolled_students_count
                )
            )
            continue

        topic_ids = [t.id for t in topics]

        # Get grades for assignments in this course
        grades_result = await db.execute(
            select(Grade)
            .join(Assignment, Grade.assignment_id == Assignment.id)
            .where(
                Grade.student_id == current_user.id,
                Assignment.topic_id.in_(topic_ids)
            )
            .options(selectinload(Grade.assignment))
            .order_by(Grade.graded_at.desc())
        )
        grades = grades_result.scalars().all()

        # Calculate average score
        average_score = None
        if grades:
            average_score = sum(g.score for g in grades) / len(grades)

        result_list.append(
            StudentCourseWithGradesResponse(
                course_id=course_id,
                course_title=course.title,
                grades=grades,
                average_score=average_score,
                grades_count=len(grades),
                enrolled_students_count=enrolled_students_count
            )
        )

    return result_list


@router.post("/enroll/{course_id}")
async def enroll_student_in_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Grants student access to a course through active study groups.
    If course is already in the student's current group pools, no extra group join is required.
    """
    # 1. Load student's active groups and their course pools.
    result = await db.execute(
        select(StudyGroup)
        .join(StudyGroup.students)
        .where(User.id == current_user.id, StudyGroup.is_active == True)
        .options(selectinload(StudyGroup.students), selectinload(StudyGroup.courses))
    )
    active_groups = result.scalars().all()

    if course_id in _collect_course_ids(active_groups):
        return {"message": f"Course {course_id} is already available through your current group(s)"}

    # 2. Find an active group that includes this course in its pool.
    result = await db.execute(
        select(StudyGroup)
        .where(
            StudyGroup.is_active == True,
            StudyGroup.courses.any(Course.id == course_id),
        )
        .options(selectinload(StudyGroup.students))
    )
    group = result.scalars().first()
    
    if not group:
        raise HTTPException(status_code=404, detail="No active group found with access to this course")

    # 3. If student is already in this group, course access is implied by this group.
    if any(s.id == current_user.id for s in group.students):
        return {"message": f"Course {course_id} is now available via group {group.name}"}

    # 4. Student can join at most 2 active groups.
    if len(active_groups) >= 2:
        raise HTTPException(
            status_code=400,
            detail="Student already has 2 active groups. Ask admin to include this course in one of your groups.",
        )

    # 5. Join matching group.
    student_result = await db.execute(
        select(User).where(User.id == current_user.id).options(selectinload(User.groups))
    )
    student = student_result.scalars().first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    group.students.append(student)
    await db.commit()
    
    return {"message": f"Successfully enrolled in course {course_id} via group {group.name}"}
