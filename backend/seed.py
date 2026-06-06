"""Idempotent seed script for first demo launch.

Creates baseline entities only if they do not exist yet:
- admin user
- teacher user
- student user
- one test study group and student membership

Run from project root:
  python -m backend.seed
"""

import asyncio
import sys
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import insert, select

# Ensure imports work when run as a script.
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.database import async_session
from backend.app.models import StudyGroup, User, UserRole, student_group_association

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


async def get_or_create_user(session, *, email: str, full_name: str, role: UserRole, password: str) -> tuple[User, bool]:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user:
        return user, False

    user = User(
        email=email,
        full_name=full_name,
        role=role,
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.flush()
    return user, True


async def get_or_create_group(session, *, name: str, teacher_id: int) -> tuple[StudyGroup, bool]:
    result = await session.execute(select(StudyGroup).where(StudyGroup.name == name))
    group = result.scalar_one_or_none()
    if group:
        return group, False

    group = StudyGroup(name=name, teacher_id=teacher_id, is_active=True)
    session.add(group)
    await session.flush()
    return group, True


async def ensure_student_membership(session, *, student_id: int, group_id: int) -> bool:
    result = await session.execute(
        select(student_group_association).where(
            student_group_association.c.student_id == student_id,
            student_group_association.c.group_id == group_id,
        )
    )
    exists = result.first() is not None
    if exists:
        return False

    await session.execute(
        insert(student_group_association).values(student_id=student_id, group_id=group_id)
    )
    return True


async def seed_data() -> None:
    created = {
        "users": 0,
        "groups": 0,
        "memberships": 0,
    }

    async with async_session() as session:
        async with session.begin():
            admin, admin_created = await get_or_create_user(
                session,
                email="admin@school.com",
                full_name="System Admin",
                role=UserRole.admin,
                password="admin123",
            )
            teacher, teacher_created = await get_or_create_user(
                session,
                email="teacher@example.com",
                full_name="Demo Teacher",
                role=UserRole.teacher,
                password="password",
            )
            student, student_created = await get_or_create_user(
                session,
                email="student@example.com",
                full_name="Demo Student",
                role=UserRole.student,
                password="password",
            )

            group, group_created = await get_or_create_group(
                session,
                name="Demo Group",
                teacher_id=teacher.id,
            )

            membership_created = await ensure_student_membership(
                session,
                student_id=student.id,
                group_id=group.id,
            )

            created["users"] += int(admin_created) + int(teacher_created) + int(student_created)
            created["groups"] += int(group_created)
            created["memberships"] += int(membership_created)

    print("[SEED] Completed successfully.")
    print(f"[SEED] New users: {created['users']}")
    print(f"[SEED] New groups: {created['groups']}")
    print(f"[SEED] New memberships: {created['memberships']}")
    print("[SEED] Demo accounts:")
    print("  admin@school.com / admin123")
    print("  teacher@example.com / password")
    print("  student@example.com / password")


if __name__ == "__main__":
    asyncio.run(seed_data())
