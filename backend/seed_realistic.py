"""
Повне реалістичне наповнення IT School.

Що робить скрипт:
  1) ВИДАЛЯЄ усі курси та всіх користувачів, КРІМ тестових акаунтів:
        admin@school.com / admin123
        teacher@example.com / password
        student@example.com / password
     (а також усі повʼязані дані: групи, розклад, відвідуваність, завдання,
      здачі, оцінки, матеріали, повідомлення).
  2) Створює 3 викладачів і 20 студентів (паролі = "password",
     пошта студентів: 1student@example.com ... 20student@example.com).
  3) Створює 5 курсів із дисциплінами, темами, завданнями та матеріалами
     (теорія + методичка + посилання).
  4) Створює 7 груп, записує студентів (6–10 на курс, ≤3 курси на студента,
     ≤2 викладачі на курс), додає демо-студента на курс Python.
  5) Генерує розклад (минулі + майбутні заняття) і відвідуваність.
  6) Створює здачі та оцінки (частину/усі оцінено) — курс «у процесі».
  7) Записує таблицю акаунтів у backend/accounts.csv.

Запуск з кореня проєкту (де лежить тека backend):
    python backend/seed_realistic.py
"""

import asyncio
import csv
import datetime
import sys
from pathlib import Path

from passlib.context import CryptContext
from sqlalchemy import insert, select, delete

# Дозволяємо імпорт пакета backend.* при запуску як скрипта.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import async_session, engine, Base  # noqa: E402
from backend.app.models import (  # noqa: E402
    User, UserRole, Course, Discipline, Topic, Assignment, AssignmentSubmission,
    Grade, StudyGroup, Schedule, Attendance, AttendanceStatus, Material, Message, MessageStatus,
    CalendarPlan, student_group_association, group_course_association,
)
import backend.seed_realistic_data as D  # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_PASSWORD_HASH = pwd_context.hash(D.DEFAULT_PASSWORD)  # хешуємо один раз


def _t(hhmm: str) -> datetime.time:
    h, m = hhmm.split(":")
    return datetime.time(int(h), int(m))


async def wipe(session):
    """Видаляє всі дані, крім тестових акаунтів."""
    # Порядок важливий через зовнішні ключі.
    await session.execute(delete(Attendance))
    await session.execute(delete(AssignmentSubmission))
    await session.execute(delete(Grade))
    await session.execute(delete(Message))
    await session.execute(delete(Schedule))
    await session.execute(delete(Material))
    await session.execute(delete(Assignment))
    await session.execute(delete(Topic))
    await session.execute(delete(CalendarPlan))
    await session.execute(delete(Discipline))
    await session.execute(delete(group_course_association))
    await session.execute(delete(student_group_association))
    await session.execute(delete(StudyGroup))
    await session.execute(delete(Course))
    await session.execute(
        delete(User).where(User.email.notin_(list(D.PROTECTED_EMAILS)))
    )


async def get_user_by_email(session, email):
    res = await session.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def create_users(session):
    """Створює викладачів і студентів. Повертає map email->User."""
    users = {}
    for t in D.TEACHERS:
        u = User(email=t["email"], full_name=t["full_name"], patronymic=t["patronymic"],
                 phone=t["phone"], role=UserRole.teacher, password_hash=_PASSWORD_HASH)
        session.add(u)
        users[t["email"]] = u
    for s in D.STUDENTS:
        dob = datetime.date.fromisoformat(s["date_of_birth"])
        u = User(email=s["email"], full_name=s["full_name"], patronymic=s["patronymic"],
                 phone=s["phone"], date_of_birth=dob,
                 role=UserRole.student, password_hash=_PASSWORD_HASH)
        session.add(u)
        users[s["email"]] = u
    await session.flush()
    return users


async def main():
    today = datetime.date.today()
    stats = {"teachers": 0, "students": 0, "courses": 0, "groups": 0,
             "topics": 0, "assignments": 0, "materials": 0,
             "schedules": 0, "attendance": 0, "submissions": 0, "grades": 0, "messages": 0}

    # Гарантуємо наявність усіх таблиць (зокрема нової `materials`),
    # навіть якщо бекенд ще жодного разу не стартував.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        async with session.begin():
            await wipe(session)

            # Тестові акаунти (залишаються).
            demo_teacher = await get_user_by_email(session, D.DEMO_TEACHER_EMAIL)
            demo_student = await get_user_by_email(session, D.DEMO_STUDENT_EMAIL)
            admin_user = await get_user_by_email(session, "admin@school.com")

            # Нові користувачі.
            users = await create_users(session)
            stats["teachers"] = len(D.TEACHERS)
            stats["students"] = len(D.STUDENTS)

            # teacher key -> User id
            tkey_to_id = {t["key"]: users[t["email"]].id for t in D.TEACHERS}
            if demo_teacher:
                tkey_to_id["DEMO"] = demo_teacher.id
            else:
                # запасний варіант, якщо демо-викладача немає
                tkey_to_id["DEMO"] = tkey_to_id["T2"]

            # student no -> User
            sno_to_user = {s["no"]: users[s["email"]] for s in D.STUDENTS}

            # ── Курси + дисципліни + теми ──────────────────────────
            course_obj = {}
            disc_obj = {}            # ckey -> Discipline
            topic_obj = {}           # (ckey, idx) -> Topic
            for c in D.COURSES:
                course = Course(title=c["title"], description=c["description"])
                session.add(course)
                await session.flush()
                course_obj[c["key"]] = course
                stats["courses"] += 1

                disc_name, topics = D.COURSE_TOPICS[c["key"]]
                disc = Discipline(name=disc_name, course_id=course.id)
                session.add(disc)
                await session.flush()
                disc_obj[c["key"]] = disc

                for idx, title in enumerate(topics):
                    tp = Topic(title=title, discipline_id=disc.id)
                    session.add(tp)
                    await session.flush()
                    topic_obj[(c["key"], idx)] = tp
                    stats["topics"] += 1

            # ── Матеріали ──────────────────────────────────────────
            for ckey, mats in D.MATERIALS.items():
                for title, body in mats:
                    session.add(Material(course_id=course_obj[ckey].id, title=title, body=body))
                    stats["materials"] += 1

            # ── Завдання ───────────────────────────────────────────
            assignment_obj = {}       # akey -> Assignment
            assignment_mode = {}      # akey -> mode
            assignment_course = {}    # akey -> ckey
            assignment_idx = {}       # akey -> idx (0..3)
            for c in D.COURSES:
                ckey = c["key"]
                for i, a in enumerate(D.assignments_for(ckey)):
                    due = today + datetime.timedelta(days=a["due"])
                    asg = Assignment(
                        title=D.assignment_title(ckey, i),
                        description=D.assignment_descr(ckey, i),
                        due_date=due,
                        topic_id=topic_obj[(ckey, a["topic"])].id,
                    )
                    session.add(asg)
                    await session.flush()
                    assignment_obj[a["key"]] = asg
                    assignment_mode[a["key"]] = a["mode"]
                    assignment_course[a["key"]] = ckey
                    assignment_idx[a["key"]] = i
                    stats["assignments"] += 1

            # ── Групи + звʼязок з курсами + запис студентів ────────
            group_obj = {}
            for g in D.GROUPS:
                grp = StudyGroup(name=g["name"], teacher_id=tkey_to_id[g["teacher"]], is_active=True)
                session.add(grp)
                await session.flush()
                group_obj[g["key"]] = grp
                stats["groups"] += 1

                # звʼязок група-курс
                await session.execute(insert(group_course_association).values(
                    group_id=grp.id, course_id=course_obj[g["course"]].id))

                # запис студентів (через таблицю звʼязку, без ORM-валідатора)
                for sno in g["students"]:
                    await session.execute(insert(student_group_association).values(
                        student_id=sno_to_user[sno].id, group_id=grp.id))

            # демо-студента додатково записуємо в групу Python (G1)
            if demo_student:
                await session.execute(insert(student_group_association).values(
                    student_id=demo_student.id, group_id=group_obj["G1"].id))

            # ── Розклад + відвідуваність ───────────────────────────
            for g in D.GROUPS:
                gkey = g["key"]
                grp = group_obj[gkey]
                teacher_id = tkey_to_id[g["teacher"]]
                disc = disc_obj[g["course"]]
                for wk in range(-D.SCHEDULE_WEEKS_BACK, D.SCHEDULE_WEEKS_FWD + 1):
                    monday = today - datetime.timedelta(days=today.weekday()) + datetime.timedelta(weeks=wk)
                    for (wd, start, end) in D.SCHEDULE_SLOTS[gkey]:
                        sdate = monday + datetime.timedelta(days=wd)
                        sched = Schedule(
                            date=sdate, time=_t(start), end_time=_t(end),
                            group_id=grp.id, teacher_id=teacher_id,
                            discipline_id=disc.id, meeting_link=D.MEETING_LINKS[gkey],
                        )
                        session.add(sched)
                        await session.flush()
                        stats["schedules"] += 1

                        # відвідуваність лише для минулих занять
                        if sdate < today:
                            seq = f"{gkey}-{sdate.isoformat()}-{start}"
                            for sno in g["students"]:
                                st = D.attendance_status(sno, seq)
                                session.add(Attendance(
                                    student_id=sno_to_user[sno].id,
                                    schedule_id=sched.id,
                                    status=AttendanceStatus(st),
                                ))
                                stats["attendance"] += 1
                            if demo_student and gkey == "G1":
                                st = D.attendance_status(900 + 0, seq)
                                session.add(Attendance(
                                    student_id=demo_student.id, schedule_id=sched.id,
                                    status=AttendanceStatus(st)))
                                stats["attendance"] += 1

            # ── Здачі та оцінки ────────────────────────────────────
            # Студенти курсу = обʼєднання студентів його груп (+ демо на PY)
            course_students = {}  # ckey -> list of (sno_or_900, User)
            for c in D.COURSES:
                seen = {}
                for g in D.GROUPS:
                    if g["course"] == c["key"]:
                        for sno in g["students"]:
                            seen[sno] = sno_to_user[sno]
                course_students[c["key"]] = list(seen.items())
            if demo_student:
                course_students["PY"].append((900, demo_student))

            for akey, asg in assignment_obj.items():
                ckey = assignment_course[akey]
                idx = assignment_idx[akey]
                mode = assignment_mode[akey]
                due = asg.due_date
                for sno, user in course_students[ckey]:
                    if not D.is_submitted(sno, akey, mode):
                        continue
                    # дата здачі: за кілька днів до дедлайну (для минулих) або зараз
                    if due < today:
                        submitted_at = datetime.datetime.combine(
                            due - datetime.timedelta(days=2), datetime.time(18, 0))
                    else:
                        submitted_at = datetime.datetime.now() - datetime.timedelta(days=1)

                    sub = AssignmentSubmission(
                        student_id=user.id,
                        assignment_id=asg.id,
                        content=D.submission_text(sno, ckey, idx),
                        file_name=D.submission_filename(sno, ckey, idx),
                        is_locked=True,
                        submitted_at=submitted_at,
                    )

                    if D.is_graded(sno, akey, mode):
                        score = D.score_for(sno, akey)
                        graded_at = submitted_at + datetime.timedelta(days=1)
                        sub.grade_status = "graded"
                        sub.grade_score = score
                        sub.grade_feedback = D.feedback_for(score)
                        sub.graded_at = graded_at
                        session.add(Grade(
                            student_id=user.id, assignment_id=asg.id,
                            score=score, feedback=D.feedback_for(score),
                            graded_at=graded_at,
                        ))
                        stats["grades"] += 1
                    session.add(sub)
                    stats["submissions"] += 1

            # ── Історія повідомлень ────────────────────────────────
            author_by_key = {
                "T1": users[D.TEACHERS[0]["email"]],
                "T2": users[D.TEACHERS[1]["email"]],
                "T3": users[D.TEACHERS[2]["email"]],
            }
            if admin_user:
                author_by_key["ADMIN"] = admin_user
            if demo_teacher:
                author_by_key["DEMO"] = demo_teacher
            default_author = users[D.TEACHERS[0]["email"]]

            # Оголошення (broadcast) — бачать студенти у сповіщеннях
            for _akey, title, body, days_ago in D.ANNOUNCEMENTS:
                author = author_by_key.get(_akey, default_author)
                ts = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=3)
                session.add(Message(
                    sender_id=author.id, receiver_id=None,
                    content=f"{title}\n\n{body}",
                    status=MessageStatus.answered, is_escalated=False, timestamp=ts,
                ))
                stats["messages"] += 1

            # Запитання студентів до викладача (вкладка «Вхідні»)
            for sender_ref, tkey, question, answer, days_ago in D.QUESTIONS:
                if sender_ref == "DEMO_STUDENT":
                    sender = demo_student
                else:
                    sender = sno_to_user.get(sender_ref)
                if not sender:
                    continue
                teacher = author_by_key.get(tkey, default_author)
                ts = datetime.datetime.now() - datetime.timedelta(days=days_ago, hours=2)
                session.add(Message(
                    sender_id=sender.id, receiver_id=teacher.id,
                    content=question, reply=answer,
                    status=MessageStatus.answered if answer else MessageStatus.pending,
                    is_escalated=True, timestamp=ts,
                ))
                stats["messages"] += 1

        # транзакцію закрито (commit)

    # ── Таблиця акаунтів у CSV ────────────────────────────────────
    rows = D.build_account_rows()
    out = Path(__file__).resolve().parent / "accounts.csv"
    fieldnames = ["Роль", "ПІБ", "По батькові", "Email", "Пароль", "Телефон",
                  "Курси (записаний)", "Курси (викладає)", "Групи"]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

    print("[SEED] Готово.")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"[SEED] Таблиця акаунтів: {out}")
    print("[SEED] Тестові акаунти збережено:")
    print("  admin@school.com / admin123")
    print("  teacher@example.com / password  (другий викладач курсу «Бази даних»)")
    print("  student@example.com / password  (записаний на курс Python)")
    print("[SEED] Нові акаунти: пароль у всіх — 'password'.")


if __name__ == "__main__":
    asyncio.run(main())
