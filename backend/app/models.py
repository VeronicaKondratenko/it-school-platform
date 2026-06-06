from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, Enum, DateTime, Time, Date, func, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship, validates
from .database import Base
import enum

# ──────────────────────────────────────────────────────────────────
# ENUMS (Must be defined FIRST before models that use them)
# ──────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"

class AttendanceStatus(str, enum.Enum):
    present = "present"
    late = "late"
    absent = "absent"

class MessageStatus(str, enum.Enum):
    pending  = "pending"
    answered = "answered"

# ──────────────────────────────────────────────────────────────────
# ASSOCIATION TABLES
# ──────────────────────────────────────────────────────────────────

# Many-to-Many association for Students and Study Groups
student_group_association = Table(
    "student_group_association",
    Base.metadata,
    Column("student_id", Integer, ForeignKey("users.id", ondelete="CASCADE")),
    Column("group_id", Integer, ForeignKey("study_groups.id", ondelete="CASCADE"))
)

# Many-to-Many association for Study Groups and Courses (course pool per group)
group_course_association = Table(
    "group_course_association",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("study_groups.id", ondelete="CASCADE")),
    Column("course_id", Integer, ForeignKey("courses.id", ondelete="CASCADE")),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    password_hash = Column(String)
    full_name = Column(String)
    patronymic = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    phone = Column(String, nullable=True)
    photo_url = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.student)
    telegram_id = Column(BigInteger, unique=True, nullable=True)

    # Relationships
    groups = relationship("StudyGroup", secondary=student_group_association, back_populates="students")
    submissions = relationship("AssignmentSubmission", back_populates="student", cascade="all, delete-orphan", passive_deletes=True)
    
    @validates("groups")
    def validate_groups_count(self, key, group):
        # We need to check if the student (role student) already has 2 active groups
        if self.role == UserRole.student:
            active_groups_count = sum(1 for g in self.groups if g.is_active)
            if active_groups_count >= 2:
                # If we're adding a new group, check if it's active
                if group.is_active:
                     raise ValueError("Student can be in maximum 2 active StudyGroups.")
        return group

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String)

    # Relationships
    disciplines = relationship("Discipline", back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
    materials = relationship("Material", back_populates="course", cascade="all, delete-orphan", passive_deletes=True)
    pool_groups = relationship("StudyGroup", secondary=group_course_association, back_populates="courses")

class Discipline(Base):
    __tablename__ = "disciplines"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"))

    # Relationships
    course = relationship("Course", back_populates="disciplines")
    topics = relationship("Topic", back_populates="discipline", cascade="all, delete-orphan", passive_deletes=True)
    calendar_plans = relationship("CalendarPlan", back_populates="discipline", cascade="all, delete-orphan", passive_deletes=True)

class Topic(Base):
    __tablename__ = "topics"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    discipline_id = Column(Integer, ForeignKey("disciplines.id", ondelete="CASCADE"))

    # Relationships
    discipline = relationship("Discipline", back_populates="topics")
    assignments = relationship("Assignment", back_populates="topic", cascade="all, delete-orphan", passive_deletes=True)

class Material(Base):
    """Text-based learning materials attached to a course (notes, links, etc.)."""
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)  # plain text or URL
    created_at = Column(DateTime, server_default=func.now())

    # Relationship
    course = relationship("Course", back_populates="materials")

class CalendarPlan(Base):
    __tablename__ = "calendar_plans"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    discipline_id = Column(Integer, ForeignKey("disciplines.id", ondelete="CASCADE"))

    # Relationships
    discipline = relationship("Discipline", back_populates="calendar_plans")

class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    description = Column(String, nullable=True)
    due_date = Column(Date, nullable=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"))

    # Relationships
    topic = relationship("Topic", back_populates="assignments")
    grades = relationship("Grade", back_populates="assignment", cascade="all, delete-orphan", passive_deletes=True)
    submissions = relationship("AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan", passive_deletes=True)


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("student_id", "assignment_id", name="uq_submission_student_assignment"),
    )

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    content = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    is_locked = Column(Boolean, default=False, nullable=False)
    grade_status = Column(String, nullable=True)
    grade_score = Column(Integer, nullable=True)
    grade_feedback = Column(String, nullable=True)
    graded_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    student = relationship("User", back_populates="submissions")
    assignment = relationship("Assignment", back_populates="submissions")

class Grade(Base):
    __tablename__ = "grades"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"))
    score = Column(Integer)  # 0-100
    feedback = Column(String, nullable=True)
    graded_at = Column(DateTime, server_default=func.now())

    # Relationships
    student = relationship("User", foreign_keys=[student_id])
    assignment = relationship("Assignment", back_populates="grades")

class StudyGroup(Base):
    __tablename__ = "study_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)

    # Relationships
    courses = relationship("Course", secondary=group_course_association, back_populates="pool_groups")
    teacher = relationship("User")
    students = relationship("User", secondary=student_group_association, back_populates="groups")

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    date = Column(Date)
    time = Column(Time)
    end_time = Column(Time, nullable=True)
    group_id = Column(Integer, ForeignKey("study_groups.id", ondelete="CASCADE"))
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    discipline_id = Column(Integer, ForeignKey("disciplines.id", ondelete="CASCADE"))
    meeting_link = Column(String, nullable=True)  # Zoom/Meet URL

    # Relationships
    group = relationship("StudyGroup")
    teacher = relationship("User")
    discipline = relationship("Discipline")

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="CASCADE"))
    status = Column(Enum(AttendanceStatus), default=AttendanceStatus.absent)

class Message(Base):
    __tablename__ = "messages"
    id           = Column(Integer, primary_key=True)
    sender_id    = Column(Integer, ForeignKey("users.id"))
    receiver_id  = Column(Integer, ForeignKey("users.id"), nullable=True)
    content      = Column(String)
    reply        = Column(String, nullable=True)
    timestamp    = Column(DateTime, server_default=func.now())
    status       = Column(Enum(MessageStatus), default=MessageStatus.pending)
    is_escalated = Column(Boolean, default=False)

    # Relationships
    sender   = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])


class TelegramLinkCode(Base):
    """One-time codes used to securely link a Telegram account to a user.

    A code is generated from the authenticated web session, stored as a SHA-256
    hash with a short expiry, and consumed once via the bot's /link command.
    Knowing only an email is no longer enough to hijack a Telegram link.
    """
    __tablename__ = "telegram_link_codes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)

    user = relationship("User")
