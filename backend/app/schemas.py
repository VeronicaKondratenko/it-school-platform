from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from .models import UserRole, AttendanceStatus
import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    patronymic: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    role: UserRole

class UserCreate(UserBase):
    password: str


class PublicRegisterRequest(BaseModel):
    """Schema for public self-registration. Intentionally has NO `role` field:
    public sign-ups are always created as students. Teacher/admin accounts are
    created only through the admin API."""
    email: EmailStr
    full_name: str
    patronymic: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    password: str = Field(min_length=8)

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    patronymic: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None


class AdminUserRoleUpdate(BaseModel):
    role: UserRole


class AdminUserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    patronymic: Optional[str] = None
    date_of_birth: Optional[datetime.date] = None
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    role: Optional[UserRole] = None

# Assignment Schemas
class AssignmentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime.date] = None
    topic_id: int
    topic_name: Optional[str] = None
    discipline_name: Optional[str] = None
    course_id: Optional[int] = None
    course_name: Optional[str] = None
    max_score: Optional[int] = None
    submitted: Optional[bool] = None
    submission_content: Optional[str] = None
    submission_file_name: Optional[str] = None
    submission_locked: Optional[bool] = None
    grade_status: Optional[str] = None
    grade_score: Optional[int] = None
    grade_feedback: Optional[str] = None
    class Config:
        from_attributes = True


class AssignmentSubmissionCreate(BaseModel):
    content: Optional[str] = None
    file_name: Optional[str] = None

# Extended Assignment Response with course/discipline info
class AssignmentWithCourseResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime.date] = None
    topic_id: int
    discipline_name: Optional[str] = None
    course_id: Optional[int] = None
    status: Optional[str] = None  # pending, submitted, graded, overdue
    priority: Optional[str] = None  # high, medium, low
    
    class Config:
        from_attributes = True

# Grade Schemas
class GradeResponse(BaseModel):
    id: int
    score: int
    feedback: Optional[str] = None
    graded_at: datetime.datetime
    assignment: AssignmentResponse
    class Config:
        from_attributes = True

# Course Schemas
class CourseBase(BaseModel):
    title: str
    description: Optional[str] = None

class CourseCreate(CourseBase):
    pass

class CourseResponse(CourseBase):
    id: int
    class Config:
        from_attributes = True


class TopicCreate(BaseModel):
    title: str
    discipline_id: int


class TopicUpdate(BaseModel):
    title: Optional[str] = None
    discipline_id: Optional[int] = None


# Material Schemas
class MaterialCreate(BaseModel):
    title: str
    body: Optional[str] = None


class MaterialResponse(BaseModel):
    id: int
    course_id: int
    title: str
    body: Optional[str] = None
    class Config:
        from_attributes = True

# Study Group Schemas
class StudyGroupBase(BaseModel):
    name: str
    teacher_id: int
    is_active: bool = True
    course_ids: List[int] = Field(default_factory=list)
    student_ids: List[int] = Field(default_factory=list)

class StudyGroupCreate(StudyGroupBase):
    pass

class StudyGroupResponse(StudyGroupBase):
    id: int
    class Config:
        from_attributes = True

class UserResponse(UserBase):
    id: int
    groups: List[StudyGroupResponse] = []
    class Config:
        from_attributes = True

class UserResponseAdmin(UserBase):
    """Admin API response with preloaded groups for table rendering"""
    id: int
    groups: List[StudyGroupResponse] = []
    class Config:
        from_attributes = True

# Discipline Schemas
class DisciplineBase(BaseModel):
    name: str
    course_id: int

class DisciplineCreate(DisciplineBase):
    pass

class DisciplineResponse(DisciplineBase):
    id: int
    class Config:
        from_attributes = True

# Schedule Schemas
class ScheduleBase(BaseModel):
    date: datetime.date
    time: datetime.time
    end_time: Optional[datetime.time] = None
    group_id: int
    teacher_id: int
    discipline_id: int
    meeting_link: Optional[str] = None  # Zoom/Meet URL

class ScheduleCreate(ScheduleBase):
    pass

class ScheduleResponse(ScheduleBase):
    id: int
    discipline_name: Optional[str] = None
    group_name: Optional[str] = None
    teacher_name: Optional[str] = None
    class Config:
        from_attributes = True

# Attendance Schemas
class AttendanceUpdate(BaseModel):
    """For manual teacher marking: pass status (present/late/absent)"""
    status: str  # "present", "late", "absent"

class AttendanceResponse(BaseModel):
    id: int
    student_id: int
    schedule_id: int
    status: str
    class Config:
        from_attributes = True

# Student Course with Grades Schema
class StudentCourseWithGradesResponse(BaseModel):
    course_id: int
    course_title: str
    grades: List[GradeResponse]
    average_score: Optional[float] = None
    grades_count: int
    enrolled_students_count: int = 0
    
    class Config:
        from_attributes = True

# Authentication Schemas
class Token(BaseModel):
    access_token: str
    token_type: str
    role: UserRole

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[UserRole] = None

# Message Schemas
class MessageCreate(BaseModel):
    content: str
    sender_id: Optional[int] = None

class MessageReply(BaseModel):
    reply: str


class PublicNotificationCreate(BaseModel):
    title: str
    message: str
    target_role: Optional[str] = "student"


class PublicNotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    timestamp: datetime.datetime
    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: int
    sender_id: Optional[int]
    receiver_id: Optional[int] = None
    sender_name: Optional[str] = None
    sender_email: Optional[EmailStr] = None
    telegram_id: Optional[int] = None
    content: str
    reply: Optional[str]
    timestamp: datetime.datetime
    status: str
    is_escalated: bool
    class Config:
        from_attributes = True

# Admin Broadcast Schema
class BroadcastRequest(BaseModel):
    """For sending broadcast notifications via Telegram to all linked users"""
    message: str
    target_role: Optional[str] = None  # "student", "teacher", "admin", or None for all

# Admin Stats Schema
class AdminStats(BaseModel):
    total_users: int
    total_students: int
    total_teachers: int
    total_courses: int
    total_groups: int
    active_groups: int
    total_schedules: int
    telegram_linked: int
