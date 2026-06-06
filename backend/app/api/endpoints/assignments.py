"""
Assignments REST API: Create, list, submit, and grade assignments.
Available for both students and teachers.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import datetime, date
from ...database import get_db
from ...models import User, Assignment, Topic, AssignmentSubmission, StudyGroup, Discipline, Course, UserRole, Grade
from ...auth import get_current_user
from ...schemas import AssignmentResponse
from ..access import (
    require_student_can_access_assignment,
    require_teacher_course_access,
    load_assignment_with_course,
)
from pydantic import BaseModel, Field
from typing import Optional, List

router = APIRouter()


# ──────────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────────
# NOTE: AssignmentResponse is imported from app.schemas (single source of truth).
# It includes course_id and max_score, which the previous local copy was silently
# dropping.


class CreateAssignmentRequest(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[date] = None
    topic_id: int


class SubmitAssignmentRequest(BaseModel):
    content: str  # Can be text, file URL, or any content
    file_name: Optional[str] = None


class GradeSubmissionRequest(BaseModel):
    score: Optional[int] = Field(default=None, ge=0, le=100)
    status: Optional[str] = None
    feedback: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[AssignmentResponse])
async def get_assignments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get assignments:
    - Students: get all assignments from their enrolled courses
    - Teachers: get all assignments from topics in their courses
    """
    
    if current_user.role == UserRole.student:
        # Get student's groups and associated courses
        student_result = await db.execute(
            select(User)
            .where(User.id == current_user.id)
            .options(selectinload(User.groups).selectinload(StudyGroup.courses))
        )
        student = student_result.scalar_one()
        
        # Collect all course IDs from student's groups
        course_ids = set()
        for group in student.groups:
            for course in group.courses:
                course_ids.add(course.id)
        
        if not course_ids:
            return []
        
        # Get all disciplines for these courses, then all topics, then assignments
        disciplines_result = await db.execute(
            select(Discipline).where(Discipline.course_id.in_(course_ids))
        )
        disciplines = disciplines_result.scalars().all()
        discipline_ids = [d.id for d in disciplines]
        
        if not discipline_ids:
            return []
        
        topics_result = await db.execute(
            select(Topic).where(Topic.discipline_id.in_(discipline_ids))
            .options(selectinload(Topic.discipline).selectinload(Discipline.course))
        )
        topics = topics_result.scalars().all()
        topic_ids = [t.id for t in topics]
        
        if not topic_ids:
            return []
        
        # Get assignments for these topics
        assignments_result = await db.execute(
            select(Assignment)
            .where(Assignment.topic_id.in_(topic_ids))
            .options(
                selectinload(Assignment.topic)
                .selectinload(Topic.discipline)
                .selectinload(Discipline.course),
                selectinload(Assignment.submissions)
            )
            .order_by(Assignment.due_date)
        )
        assignments = assignments_result.scalars().all()
        
        # Build response with student's submission info
        response = []
        for assignment in assignments:
            # Check if student submitted
            student_submission = next(
                (s for s in assignment.submissions if s.student_id == current_user.id),
                None
            )
            
            response.append(AssignmentResponse(
                id=assignment.id,
                title=assignment.title,
                description=assignment.description,
                due_date=assignment.due_date,
                topic_id=assignment.topic_id,
                topic_name=assignment.topic.title if assignment.topic else None,
                discipline_name=assignment.topic.discipline.name if assignment.topic and assignment.topic.discipline else None,
                course_id=assignment.topic.discipline.course_id if assignment.topic and assignment.topic.discipline else None,
                course_name=assignment.topic.discipline.course.title if assignment.topic and assignment.topic.discipline and assignment.topic.discipline.course else None,
                max_score=getattr(assignment, 'max_score', None),
                submitted=student_submission is not None,
                submission_content=student_submission.content if student_submission else None,
                submission_file_name=student_submission.file_name if student_submission else None,
                submission_locked=student_submission.is_locked if student_submission else None,
                grade_status=student_submission.grade_status if student_submission else None,
                grade_score=student_submission.grade_score if student_submission else None,
                grade_feedback=student_submission.grade_feedback if student_submission else None,
            ))
        
        return response
    
    elif current_user.role == UserRole.teacher:
        # Get teacher's groups
        groups_result = await db.execute(
            select(StudyGroup)
            .where(StudyGroup.teacher_id == current_user.id)
            .options(selectinload(StudyGroup.courses))
        )
        groups = groups_result.scalars().all()
        
        # Collect course IDs
        course_ids = set()
        for group in groups:
            for course in group.courses:
                course_ids.add(course.id)
        
        if not course_ids:
            return []
        
        # Get disciplines for these courses
        disciplines_result = await db.execute(
            select(Discipline).where(Discipline.course_id.in_(course_ids))
        )
        disciplines = disciplines_result.scalars().all()
        discipline_ids = [d.id for d in disciplines]
        
        if not discipline_ids:
            return []
        
        # Get topics
        topics_result = await db.execute(
            select(Topic).where(Topic.discipline_id.in_(discipline_ids))
            .options(selectinload(Topic.discipline).selectinload(Discipline.course))
        )
        topics = topics_result.scalars().all()
        topic_ids = [t.id for t in topics]
        
        if not topic_ids:
            return []
        
        # Get assignments
        assignments_result = await db.execute(
            select(Assignment)
            .where(Assignment.topic_id.in_(topic_ids))
            .options(
                selectinload(Assignment.topic)
                .selectinload(Topic.discipline)
                .selectinload(Discipline.course)
            )
            .order_by(Assignment.due_date)
        )
        assignments = assignments_result.scalars().all()
        
        return [
            AssignmentResponse(
                id=a.id,
                title=a.title,
                description=a.description,
                due_date=a.due_date,
                topic_id=a.topic_id,
                topic_name=a.topic.title if a.topic else None,
                discipline_name=a.topic.discipline.name if a.topic and a.topic.discipline else None,
                course_id=a.topic.discipline.course_id if a.topic and a.topic.discipline else None,
                course_name=a.topic.discipline.course.title if a.topic and a.topic.discipline and a.topic.discipline.course else None,
                max_score=getattr(a, 'max_score', None),
            )
            for a in assignments
        ]
    
    return []


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get assignment details"""
    assignment_result = await db.execute(
        select(Assignment)
        .where(Assignment.id == assignment_id)
        .options(
            selectinload(Assignment.topic)
            .selectinload(Topic.discipline)
            .selectinload(Discipline.course),
            selectinload(Assignment.submissions)
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # For students, check if they can see this assignment (in their course)
    if current_user.role == UserRole.student:
        # Verify student is in a group for this course
        student_result = await db.execute(
            select(User)
            .where(User.id == current_user.id)
            .options(
                selectinload(User.groups).selectinload(StudyGroup.courses)
            )
        )
        student = student_result.scalar_one()
        
        course_ids = set()
        for group in student.groups:
            for course in group.courses:
                course_ids.add(course.id)
        
        if assignment.topic.discipline.course_id not in course_ids:
            raise HTTPException(status_code=403, detail="Not authorized to view this assignment")

    # A04: teachers may only view assignments of courses they teach (admins: any).
    if current_user.role == UserRole.teacher:
        await require_teacher_course_access(db, current_user, assignment.topic.discipline.course_id)
    
    # Get student submission if exists
    student_submission = None
    if current_user.role == UserRole.student:
        student_submission = next(
            (s for s in assignment.submissions if s.student_id == current_user.id),
            None
        )
    
    return AssignmentResponse(
        id=assignment.id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        topic_id=assignment.topic_id,
        topic_name=assignment.topic.title,
        discipline_name=assignment.topic.discipline.name,
        course_name=assignment.topic.discipline.course.title,
        course_id=assignment.topic.discipline.course_id,
        max_score=getattr(assignment, "max_score", None),
        submitted=student_submission is not None,
        submission_content=student_submission.content if student_submission else None,
        submission_file_name=student_submission.file_name if student_submission else None,
        submission_locked=student_submission.is_locked if student_submission else None,
        grade_status=student_submission.grade_status if student_submission else None,
        grade_score=student_submission.grade_score if student_submission else None,
        grade_feedback=student_submission.grade_feedback if student_submission else None,
    )


@router.post("/", response_model=AssignmentResponse)
async def create_assignment(
    req: CreateAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create new assignment (teacher only)"""
    
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(
            status_code=403,
            detail="Only teachers or admins can create assignments"
        )
    
    # Verify topic exists; teacher must teach this course (admin: any)
    topic_result = await db.execute(
        select(Topic)
        .where(Topic.id == req.topic_id)
        .options(
            selectinload(Topic.discipline)
            .selectinload(Discipline.course)
        )
    )
    topic = topic_result.scalar_one_or_none()
    
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    await require_teacher_course_access(db, current_user, topic.discipline.course_id)
    
    # Create assignment
    assignment = Assignment(
        title=req.title,
        description=req.description,
        due_date=req.due_date,
        topic_id=req.topic_id,
    )
    
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment, [
        'topic',
    ])
    await db.commit()
    
    return AssignmentResponse(
        id=assignment.id,
        title=assignment.title,
        description=assignment.description,
        due_date=assignment.due_date,
        topic_id=assignment.topic_id,
        topic_name=topic.title,
        discipline_name=topic.discipline.name,
        course_name=topic.discipline.course.title,
    )


@router.post("/{assignment_id}/submit", response_model=dict)
async def submit_assignment(
    assignment_id: int,
    req: SubmitAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit assignment (student only)"""
    
    if current_user.role != UserRole.student:
        raise HTTPException(
            status_code=403,
            detail="Only students can submit assignments"
        )

    # Load the assignment together with its course, then verify the student is
    # actually enrolled in that course before allowing a submission.
    assignment = await load_assignment_with_course(db, assignment_id)
    await require_student_can_access_assignment(db, current_user.id, assignment)
    
    # Create or update submission
    submission_result = await db.execute(
        select(AssignmentSubmission).where(
            and_(
                AssignmentSubmission.student_id == current_user.id,
                AssignmentSubmission.assignment_id == assignment_id,
            )
        )
    )
    submission = submission_result.scalar_one_or_none()
    
    if submission:
        if submission.is_locked:
            raise HTTPException(
                status_code=400,
                detail="Submission is locked. Ask teacher to reset before resubmitting"
            )

        # Update existing submission
        submission.content = req.content
        submission.file_name = req.file_name
        submission.is_locked = True
        submission.submitted_at = datetime.now()
    else:
        # Create new submission
        submission = AssignmentSubmission(
            student_id=current_user.id,
            assignment_id=assignment_id,
            content=req.content,
            file_name=req.file_name,
            is_locked=True,
        )
        db.add(submission)
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Assignment submitted successfully",
        "submission_id": submission.id,
        "file_name": submission.file_name,
        "locked": submission.is_locked,
    }


@router.get("/{assignment_id}/submissions", response_model=list)
async def get_assignment_submissions(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all submissions for an assignment (teacher only)"""
    
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(
            status_code=403,
            detail="Only teachers can view submissions"
        )
    
    # Verify assignment exists and is in teacher's course
    assignment_result = await db.execute(
        select(Assignment)
        .where(Assignment.id == assignment_id)
        .options(
            selectinload(Assignment.topic)
            .selectinload(Topic.discipline)
            .selectinload(Discipline.course)
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check if teacher teaches this course
    groups_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.teacher_id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = groups_result.scalars().all()
    
    course_ids = set()
    for group in groups:
        for course in group.courses:
            course_ids.add(course.id)
    
    if current_user.role == UserRole.teacher and assignment.topic.discipline.course_id not in course_ids:
        raise HTTPException(
            status_code=403,
            detail="You don't teach this course"
        )
    
    # Get submissions
    submissions_result = await db.execute(
        select(AssignmentSubmission)
        .where(AssignmentSubmission.assignment_id == assignment_id)
        .options(selectinload(AssignmentSubmission.student))
        .order_by(AssignmentSubmission.submitted_at.desc())
    )
    submissions = submissions_result.scalars().all()
    
    return [
        {
            "id": s.id,
            "submission_id": s.id,
            "student_id": s.student_id,
            "student_name": s.student.full_name,
            "content": s.content,
            "file_name": s.file_name,
            "is_locked": s.is_locked,
            "grade_status": s.grade_status,
            "grade_score": s.grade_score,
            "grade_feedback": s.grade_feedback,
            "submitted_at": s.submitted_at.isoformat(),
        }
        for s in submissions
    ]


@router.post("/submissions/{submission_id}/grade", response_model=dict)
async def grade_submission(
    submission_id: int,
    req: GradeSubmissionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or admin access required")

    submission_result = await db.execute(
        select(AssignmentSubmission)
        .where(AssignmentSubmission.id == submission_id)
        .options(
            selectinload(AssignmentSubmission.assignment)
            .selectinload(Assignment.topic)
            .selectinload(Topic.discipline)
        )
    )
    submission = submission_result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    groups_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.teacher_id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = groups_result.scalars().all()
    course_ids = {course.id for group in groups for course in group.courses}

    submission_course_id = (
        submission.assignment.topic.discipline.course_id
        if submission.assignment and submission.assignment.topic and submission.assignment.topic.discipline
        else None
    )
    if current_user.role == UserRole.teacher and submission_course_id not in course_ids:
        raise HTTPException(status_code=403, detail="You don't teach this course")

    existing_grade_result = await db.execute(
        select(Grade).where(
            Grade.student_id == submission.student_id,
            Grade.assignment_id == submission.assignment_id,
        )
    )
    existing_grade = existing_grade_result.scalar_one_or_none()

    # Single source of truth: keep Grade.score and submission.grade_score equal.
    # If the teacher submits feedback without a score, we DON'T wipe an existing
    # grade — we keep the previous score so the two tables never diverge.
    if existing_grade:
        if req.score is not None:
            existing_grade.score = req.score
        existing_grade.feedback = req.feedback
        existing_grade.graded_at = datetime.now()
        effective_score = existing_grade.score
    else:
        effective_score = req.score
        if req.score is not None:
            db.add(
                Grade(
                    student_id=submission.student_id,
                    assignment_id=submission.assignment_id,
                    score=req.score,
                    feedback=req.feedback,
                    graded_at=datetime.now(),
                )
            )

    submission.grade_status = req.status or ("graded" if effective_score is not None else "reviewed")
    submission.grade_score = effective_score
    submission.grade_feedback = req.feedback
    submission.graded_at = datetime.now()
    submission.is_locked = True

    await db.commit()
    return {
        "success": True,
        "submission_id": submission.id,
        "grade_status": submission.grade_status,
        "grade_score": submission.grade_score,
    }


@router.post("/submissions/{submission_id}/reset", response_model=dict)
async def reset_submission_lock(
    submission_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or admin access required")

    submission_result = await db.execute(
        select(AssignmentSubmission)
        .where(AssignmentSubmission.id == submission_id)
        .options(
            selectinload(AssignmentSubmission.assignment)
            .selectinload(Assignment.topic)
            .selectinload(Topic.discipline)
        )
    )
    submission = submission_result.scalar_one_or_none()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    groups_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.teacher_id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = groups_result.scalars().all()
    course_ids = {course.id for group in groups for course in group.courses}

    submission_course_id = (
        submission.assignment.topic.discipline.course_id
        if submission.assignment and submission.assignment.topic and submission.assignment.topic.discipline
        else None
    )
    if current_user.role == UserRole.teacher and submission_course_id not in course_ids:
        raise HTTPException(status_code=403, detail="You don't teach this course")

    submission.is_locked = False
    await db.commit()

    return {
        "success": True,
        "submission_id": submission.id,
        "locked": submission.is_locked,
    }


@router.delete("/{assignment_id}", response_model=dict)
async def delete_assignment(
    assignment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.teacher, UserRole.admin]:
        raise HTTPException(status_code=403, detail="Teacher or admin access required")

    assignment_result = await db.execute(
        select(Assignment)
        .where(Assignment.id == assignment_id)
        .options(
            selectinload(Assignment.topic)
            .selectinload(Topic.discipline)
        )
    )
    assignment = assignment_result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    groups_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.teacher_id == current_user.id)
        .options(selectinload(StudyGroup.courses))
    )
    groups = groups_result.scalars().all()
    course_ids = {course.id for group in groups for course in group.courses}

    assignment_course_id = (
        assignment.topic.discipline.course_id
        if assignment.topic and assignment.topic.discipline
        else None
    )
    if current_user.role == UserRole.teacher and assignment_course_id not in course_ids:
        raise HTTPException(status_code=403, detail="You don't teach this course")

    submissions_result = await db.execute(
        select(AssignmentSubmission).where(AssignmentSubmission.assignment_id == assignment_id)
    )
    for submission in submissions_result.scalars().all():
        await db.delete(submission)

    grades_result = await db.execute(
        select(Grade).where(Grade.assignment_id == assignment_id)
    )
    for grade in grades_result.scalars().all():
        await db.delete(grade)

    await db.delete(assignment)
    await db.commit()

    return {"success": True, "message": "Assignment deleted", "assignment_id": assignment_id}
