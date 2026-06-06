from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from ...database import get_db
from ...models import Course, Discipline, Topic, User, UserRole, Material, StudyGroup
from ...schemas import CourseCreate, CourseResponse, TopicCreate, TopicUpdate, MaterialCreate, MaterialResponse
from ...auth import get_current_user, get_current_admin
from ..access import require_teacher_course_access, require_course_read_access

router = APIRouter()

@router.get("/", response_model=List[CourseResponse])
async def get_courses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Course))
    return result.scalars().all()


@router.get("/public", response_model=List[CourseResponse])
async def get_public_courses(db: AsyncSession = Depends(get_db)):
    """Public marketing catalog (id/title/description only). Safe for the landing
    page; does not expose groups, students or other internal relations."""
    result = await db.execute(select(Course))
    return result.scalars().all()


@router.get("/{course_id}/topics")
async def get_course_topics(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    # Only enrolled students / teaching teachers / admins may read course content.
    await require_course_read_access(db, current_user, course_id)

    topics_result = await db.execute(
        select(Topic, Discipline.name)
        .join(Discipline, Topic.discipline_id == Discipline.id)
        .where(Discipline.course_id == course_id)
        .order_by(Discipline.name, Topic.title)
    )
    topic_rows = topics_result.all()

    return [
        {
            "id": topic.id,
            "title": topic.title,
            "discipline_name": discipline_name,
            "discipline_id": topic.discipline_id,
            "course_id": course_id,
        }
        for topic, discipline_name in topic_rows
    ]


@router.post("/{course_id}/topics")
async def create_course_topic(
    course_id: int,
    payload: TopicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can create topics")
    await require_teacher_course_access(db, current_user, course_id)

    course_result = await db.execute(select(Course).where(Course.id == course_id))
    course = course_result.scalars().first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    discipline_result = await db.execute(
        select(Discipline).where(Discipline.id == payload.discipline_id, Discipline.course_id == course_id)
    )
    discipline = discipline_result.scalars().first()
    if not discipline:
        raise HTTPException(status_code=404, detail="Discipline not found for this course")

    topic = Topic(title=payload.title, discipline_id=payload.discipline_id)
    db.add(topic)
    await db.commit()
    await db.refresh(topic)

    return {"id": topic.id, "title": topic.title, "discipline_id": topic.discipline_id, "course_id": course_id}


@router.put("/topics/{topic_id}")
async def update_course_topic(
    topic_id: int,
    payload: TopicUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can update topics")

    topic_result = await db.execute(select(Topic).where(Topic.id == topic_id).options(selectinload(Topic.discipline)))
    topic = topic_result.scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.discipline is not None:
        await require_teacher_course_access(db, current_user, topic.discipline.course_id)

    if payload.title is not None:
        topic.title = payload.title
    if payload.discipline_id is not None:
        discipline_result = await db.execute(select(Discipline).where(Discipline.id == payload.discipline_id))
        discipline = discipline_result.scalars().first()
        if not discipline:
            raise HTTPException(status_code=404, detail="Discipline not found")
        # Moving a topic into another discipline requires access to the TARGET
        # discipline's course too (prevents moving topics into someone else's course).
        await require_teacher_course_access(db, current_user, discipline.course_id)
        topic.discipline_id = payload.discipline_id

    await db.commit()
    return {"id": topic.id, "title": topic.title, "discipline_id": topic.discipline_id}


@router.delete("/topics/{topic_id}")
async def delete_course_topic(
    topic_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can delete topics")

    topic_result = await db.execute(select(Topic).where(Topic.id == topic_id).options(selectinload(Topic.discipline)))
    topic = topic_result.scalars().first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if topic.discipline is not None:
        await require_teacher_course_access(db, current_user, topic.discipline.course_id)

    await db.delete(topic)
    await db.commit()
    return {"message": "Topic deleted"}

@router.get("/{course_id}/materials", response_model=List[MaterialResponse])
async def get_course_materials(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    if not course_result.scalars().first():
        raise HTTPException(status_code=404, detail="Course not found")
    await require_course_read_access(db, current_user, course_id)

    result = await db.execute(
        select(Material).where(Material.course_id == course_id).order_by(Material.id.desc())
    )
    return result.scalars().all()


@router.post("/{course_id}/materials", response_model=MaterialResponse)
async def create_course_material(
    course_id: int,
    payload: MaterialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can add materials")
    await require_teacher_course_access(db, current_user, course_id)

    course_result = await db.execute(select(Course).where(Course.id == course_id))
    if not course_result.scalars().first():
        raise HTTPException(status_code=404, detail="Course not found")

    if not (payload.title or "").strip():
        raise HTTPException(status_code=400, detail="Material title is required")

    material = Material(course_id=course_id, title=payload.title.strip(), body=(payload.body or "").strip())
    db.add(material)
    await db.commit()
    await db.refresh(material)
    return material


@router.delete("/{course_id}/materials/{material_id}")
async def delete_course_material(
    course_id: int,
    material_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can delete materials")
    await require_teacher_course_access(db, current_user, course_id)

    result = await db.execute(
        select(Material).where(Material.id == material_id, Material.course_id == course_id)
    )
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    await db.delete(material)
    await db.commit()
    return {"message": "Material deleted"}


@router.get("/{course_id}/teacher")
async def get_course_teacher(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the teacher(s) that lead the group(s) which include this course.

    Used on the course "Information" tab so students know who answers their
    questions in Telegram.
    """
    course_result = await db.execute(select(Course).where(Course.id == course_id))
    if not course_result.scalars().first():
        raise HTTPException(status_code=404, detail="Course not found")

    # Only enrolled students / teaching teachers / admins may see the teacher info.
    await require_course_read_access(db, current_user, course_id)

    groups_result = await db.execute(
        select(StudyGroup)
        .where(StudyGroup.courses.any(Course.id == course_id))
        .options(selectinload(StudyGroup.teacher))
    )
    teachers = []
    seen = set()
    for group in groups_result.scalars().all():
        t = group.teacher
        if t and t.id not in seen:
            seen.add(t.id)
            full = t.full_name or ""
            if t.patronymic:
                full = f"{full} {t.patronymic}".strip()
            teachers.append({"id": t.id, "full_name": full, "email": t.email})

    return {"teachers": teachers}


@router.post("/", response_model=CourseResponse)
async def create_course(
    course: CourseCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Only admin can create courses")

    db_course = Course(**course.dict())
    db.add(db_course)
    await db.commit()
    await db.refresh(db_course)
    return db_course

@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: int,
    course_update: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.admin, UserRole.teacher]:
        raise HTTPException(status_code=403, detail="Only admin or teacher can update courses")
    await require_teacher_course_access(db, current_user, course_id)

    result = await db.execute(select(Course).where(Course.id == course_id))
    db_course = result.scalars().first()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    for key, value in course_update.dict().items():
        setattr(db_course, key, value)
    
    await db.commit()
    await db.refresh(db_course)
    return db_course

@router.delete("/{course_id}")
async def delete_course(
    course_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    
    result = await db.execute(select(Course).where(Course.id == course_id))
    db_course = result.scalars().first()
    if not db_course:
        raise HTTPException(status_code=404, detail="Course not found")
    
    await db.delete(db_course)
    await db.commit()
    return {"message": "Course deleted"}
