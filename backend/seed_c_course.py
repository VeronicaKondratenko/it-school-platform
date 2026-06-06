"""
Seed script — Курс «Мова програмування C»
Заповнює базу повноцінним курсом з усіма можливостями платформи:
  - Курс, 3 дисципліни, 9 тем
  - 9 завдань різного рівня
  - Розклад занять на 4 тижні
  - Демо-здачі від студента
  - Оцінки

Запуск:
  python -m backend.seed_c_course
"""

import asyncio, sys
from datetime import date, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, insert
from backend.app.database import async_session
from backend.app.models import (
    User, UserRole, Course, Discipline, Topic, Assignment,
    AssignmentSubmission, Grade, StudyGroup, Schedule,
    group_course_association, student_group_association,
)

# ─────────────────────────────────────────────────────────────────────────────
# Course content
# ─────────────────────────────────────────────────────────────────────────────
COURSE = dict(
    title="Мова програмування C",
    description=(
        "Фундаментальний курс мови C — від змінних і покажчиків до "
        "динамічної пам'яті та структур даних. Курс охоплює синтаксис, "
        "управління пам'яттю, роботу з файлами та алгоритмічне мислення."
    ),
)

DISCIPLINES = [
    dict(name="Основи мови C"),
    dict(name="Покажчики та пам'ять"),
    dict(name="Структури даних та файли"),
]

# topics per discipline
TOPICS = {
    "Основи мови C": [
        dict(title="Вступ до C. Перша програма. gcc/clang"),
        dict(title="Типи даних, змінні, оператори"),
        dict(title="Умовні оператори та цикли"),
    ],
    "Покажчики та пам'ять": [
        dict(title="Покажчики: основи та арифметика"),
        dict(title="Масиви та рядки (char-масиви)"),
        dict(title="Динамічна пам'ять: malloc/calloc/free"),
    ],
    "Структури даних та файли": [
        dict(title="Структури (struct) та об'єднання (union)"),
        dict(title="Файловий ввід/вивід: fopen, fread, fwrite"),
        dict(title="Алгоритми сортування на C"),
    ],
}

# assignments per topic
ASSIGNMENTS = {
    "Вступ до C. Перша програма. gcc/clang": [
        dict(
            title="Hello, World! та компіляція",
            description=(
                "1. Напишіть програму, яка виводить: 'Hello, World!'\n"
                "2. Скомпілюйте через gcc: gcc main.c -o hello\n"
                "3. Запустіть та зробіть скріншот терміналу.\n\n"
                "📎 Здайте: посилання на код (GitHub Gist або текст програми)."
            ),
            due_offset=7,
            max_score=100,
        ),
        dict(
            title="Методичка: Структура програми на C",
            description=(
                "📖 МЕТОДИЧКА — прочитайте перед виконанням завдань\n\n"
                "Структура типової програми на C:\n\n"
                "#include <stdio.h>   // підключення бібліотек\n\n"
                "int main() {         // головна функція\n"
                "    // код програми\n"
                "    return 0;        // код повернення\n"
                "}\n\n"
                "Компіляція: gcc -Wall -o program main.c\n"
                "Запуск:     ./program\n\n"
                "✅ Виконайте: напишіть та запустіть цей код, надішліть скріншот."
            ),
            due_offset=5,
            max_score=50,
        ),
    ],
    "Типи даних, змінні, оператори": [
        dict(
            title="Калькулятор на C",
            description=(
                "Напишіть консольний калькулятор, що:\n"
                "• Читає два числа (float) і оператор (+, -, *, /)\n"
                "• Виводить результат\n"
                "• Обробляє ділення на нуль\n\n"
                "Приклад виводу:\n"
                "Введіть вираз: 10 / 3\n"
                "Результат: 3.333333\n\n"
                "📎 Здайте вихідний код."
            ),
            due_offset=10,
            max_score=100,
        ),
    ],
    "Умовні оператори та цикли": [
        dict(
            title="Числа Фібоначчі та таблиця множення",
            description=(
                "Реалізуйте дві задачі:\n\n"
                "1. Числа Фібоначчі — виведіть перші N чисел (N вводить користувач)\n"
                "2. Таблиця множення — виведіть таблицю N×N через вкладені цикли\n\n"
                "Використовуйте: for, while, if-else\n\n"
                "📎 Здайте: один файл з двома функціями + main()."
            ),
            due_offset=14,
            max_score=100,
        ),
    ],
    "Покажчики: основи та арифметика": [
        dict(
            title="Робота з покажчиками",
            description=(
                "Виконайте завдання:\n\n"
                "1. Створіть функцію swap(int *a, int *b) — обмін значень без тимчасової змінної\n"
                "2. Напишіть функцію що повертає покажчик на максимальний елемент масиву\n"
                "3. Продемонструйте різницю між *ptr++ і (*ptr)++\n\n"
                "⚠️ Кожне завдання — окрема функція з поясненням у коментарях.\n\n"
                "📎 Здайте .c файл."
            ),
            due_offset=14,
            max_score=100,
        ),
    ],
    "Масиви та рядки (char-масиви)": [
        dict(
            title="Обробка рядків без string.h",
            description=(
                "Реалізуйте власні версії стандартних функцій:\n\n"
                "• my_strlen(char *s) — довжина рядка\n"
                "• my_strcpy(char *dst, char *src) — копіювання\n"
                "• my_strrev(char *s) — реверс рядка in-place\n"
                "• my_toupper(char *s) — переведення у верхній регістр\n\n"
                "Тест: перевірте кожну функцію у main() з прикладами.\n\n"
                "📎 Здайте вихідний код."
            ),
            due_offset=14,
            max_score=100,
        ),
    ],
    "Динамічна пам'ять: malloc/calloc/free": [
        dict(
            title="Динамічний масив",
            description=(
                "Реалізуйте динамічний масив цілих чисел:\n\n"
                "typedef struct {\n"
                "    int *data;\n"
                "    size_t size;\n"
                "    size_t capacity;\n"
                "} DynArray;\n\n"
                "Функції:\n"
                "• da_init(DynArray *da)\n"
                "• da_push(DynArray *da, int val) — з авто-розширенням ×2\n"
                "• da_get(DynArray *da, size_t i)\n"
                "• da_free(DynArray *da)\n\n"
                "Перевірте на витоки пам'яті через valgrind.\n\n"
                "📎 Здайте .c + .h файли (або один .c)."
            ),
            due_offset=21,
            max_score=100,
        ),
    ],
    "Структури (struct) та об'єднання (union)": [
        dict(
            title="База даних студентів",
            description=(
                "Створіть програму управління записами студентів:\n\n"
                "typedef struct {\n"
                "    int id;\n"
                "    char name[64];\n"
                "    float gpa;\n"
                "    int year;\n"
                "} Student;\n\n"
                "Реалізуйте:\n"
                "• Додавання студента\n"
                "• Пошук за іменем\n"
                "• Виведення всіх (відсортованих за GPA)\n"
                "• Збереження/завантаження з файлу (бінарно)\n\n"
                "📎 Здайте повний проєкт."
            ),
            due_offset=21,
            max_score=100,
        ),
    ],
    "Файловий ввід/вивід: fopen, fread, fwrite": [
        dict(
            title="Утиліта обробки CSV",
            description=(
                "Напишіть програму що читає CSV-файл формату:\n"
                "id,name,score\n"
                "1,Alice,92\n"
                "2,Bob,78\n\n"
                "Програма повинна:\n"
                "• Читати файл через fopen/fgets\n"
                "• Парсити рядки (strtok)\n"
                "• Виводити відсортовані за score записи\n"
                "• Записувати результат у новий файл\n\n"
                "📎 Здайте .c файл + тестовий .csv."
            ),
            due_offset=28,
            max_score=100,
        ),
    ],
    "Алгоритми сортування на C": [
        dict(
            title="Порівняння алгоритмів сортування",
            description=(
                "Реалізуйте та порівняйте 3 алгоритми:\n\n"
                "1. Bubble Sort\n"
                "2. Quick Sort (рекурсивний)\n"
                "3. Merge Sort\n\n"
                "Для кожного:\n"
                "• Реалізація на масиві int[]\n"
                "• Підрахунок кількості порівнянь\n"
                "• Вимірювання часу (clock())\n\n"
                "Тест: масиви розміром 1000, 10000, 100000 елементів.\n"
                "Виведіть таблицю результатів.\n\n"
                "📎 Здайте .c файл зі звітом у коментарях."
            ),
            due_offset=28,
            max_score=100,
        ),
    ],
}


async def get_or_create(session, model, filter_kwargs, create_kwargs=None):
    result = await session.execute(select(model).filter_by(**filter_kwargs))
    obj = result.scalar_one_or_none()
    if obj:
        return obj, False
    obj = model(**(filter_kwargs | (create_kwargs or {})))
    session.add(obj)
    await session.flush()
    return obj, True


async def seed():
    print("=" * 60)
    print("  IT School — Seed: Курс «Мова C»")
    print("=" * 60)

    async with async_session() as session:
        async with session.begin():

            # ── users ──────────────────────────────────────────────────
            from passlib.context import CryptContext
            pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

            teacher, _ = await get_or_create(session, User,
                {"email": "teacher@example.com"},
                {"full_name": "Ivan Ivanov", "role": UserRole.teacher,
                 "password_hash": pwd.hash("password")})

            student, _ = await get_or_create(session, User,
                {"email": "student@example.com"},
                {"full_name": "Test Student", "role": UserRole.student,
                 "password_hash": pwd.hash("password")})

            print(f"  👤 teacher: {teacher.id}  student: {student.id}")

            # ── course ─────────────────────────────────────────────────
            course, created = await get_or_create(session, Course,
                {"title": COURSE["title"]},
                {"description": COURSE["description"]})
            print(f"  📚 Course id={course.id} ({'new' if created else 'exists'})")

            # ── group ──────────────────────────────────────────────────
            group, _ = await get_or_create(session, StudyGroup,
                {"name": "C-програмування 2026"},
                {"teacher_id": teacher.id, "is_active": True})
            print(f"  👥 Group id={group.id}")

            # link course ↔ group
            r = await session.execute(
                select(group_course_association).where(
                    group_course_association.c.group_id == group.id,
                    group_course_association.c.course_id == course.id,
                ))
            if not r.first():
                await session.execute(group_course_association.insert().values(
                    group_id=group.id, course_id=course.id))

            # enroll student
            r = await session.execute(
                select(student_group_association).where(
                    student_group_association.c.student_id == student.id,
                    student_group_association.c.group_id == group.id,
                ))
            if not r.first():
                await session.execute(student_group_association.insert().values(
                    student_id=student.id, group_id=group.id))

            # ── disciplines, topics, assignments ───────────────────────
            topic_map = {}   # title → Topic
            for disc_data in DISCIPLINES:
                disc, _ = await get_or_create(session, Discipline,
                    {"name": disc_data["name"], "course_id": course.id})

                for top_data in TOPICS.get(disc_data["name"], []):
                    topic, _ = await get_or_create(session, Topic,
                        {"title": top_data["title"], "discipline_id": disc.id})
                    topic_map[top_data["title"]] = topic

                    for asgn_data in ASSIGNMENTS.get(top_data["title"], []):
                        due = date.today() + timedelta(days=asgn_data["due_offset"])
                        asgn, a_new = await get_or_create(session, Assignment,
                            {"title": asgn_data["title"], "topic_id": topic.id},
                            {"description": asgn_data["description"], "due_date": due})
                        if a_new:
                            print(f"    📝 Assignment: {asgn_data['title'][:50]}")

            # ── schedule (4 weeks, Mon+Wed+Fri) ───────────────────────
            topics_list = list(topic_map.values())
            disc_ids = {t.id: t.discipline_id for t in topics_list}

            today = date.today()
            monday = today - timedelta(days=today.weekday())  # this week's Monday
            sched_count = 0
            for week in range(4):
                for day_offset, hour in [(0, 9), (2, 11), (4, 14)]:  # Mon, Wed, Fri
                    lesson_date = monday + timedelta(weeks=week, days=day_offset)
                    idx = (week * 3 + day_offset // 2) % len(topics_list)
                    topic = topics_list[idx]
                    r = await session.execute(
                        select(Schedule).where(
                            Schedule.group_id == group.id,
                            Schedule.date == lesson_date,
                            Schedule.time == time(hour, 0),
                        ))
                    if not r.scalar_one_or_none():
                        session.add(Schedule(
                            date=lesson_date,
                            time=time(hour, 0),
                            end_time=time(hour + 1, 30),
                            group_id=group.id,
                            teacher_id=teacher.id,
                            discipline_id=topic.discipline_id,
                            meeting_link="https://meet.google.com/c-course-demo",
                        ))
                        sched_count += 1
            print(f"  📅 Schedule: +{sched_count} new lessons")

            # ── demo submissions from student ─────────────────────────
            # Get all assignments for this course
            all_topics_ids = [t.id for t in topics_list]
            asgn_result = await session.execute(
                select(Assignment).where(Assignment.topic_id.in_(all_topics_ids)))
            all_assignments = asgn_result.scalars().all()

            sub_count = 0
            for i, asgn in enumerate(all_assignments[:5]):  # first 5 get submissions
                r = await session.execute(
                    select(AssignmentSubmission).where(
                        AssignmentSubmission.student_id == student.id,
                        AssignmentSubmission.assignment_id == asgn.id,
                    ))
                if r.scalar_one_or_none():
                    continue
                sample_answers = [
                    "#include <stdio.h>\nint main() {\n    printf(\"Hello, World!\\n\");\n    return 0;\n}",
                    "float calc(float a, char op, float b) {\n    if(op=='+') return a+b;\n    if(op=='-') return a-b;\n    if(op=='*') return a*b;\n    if(op=='/' && b!=0) return a/b;\n    return 0;\n}",
                    "void fib(int n) {\n    int a=0,b=1;\n    for(int i=0;i<n;i++){\n        printf(\"%d \",a);\n        int t=a+b; a=b; b=t;\n    }\n}",
                    "void swap(int *a, int *b) {\n    *a ^= *b;\n    *b ^= *a;\n    *a ^= *b;\n}",
                    "int my_strlen(char *s) {\n    int n=0;\n    while(*s++) n++;\n    return n;\n}",
                ]
                is_graded = i < 3
                session.add(AssignmentSubmission(
                    student_id=student.id,
                    assignment_id=asgn.id,
                    content=sample_answers[i % len(sample_answers)],
                    file_name=f"lab{i+1}_solution.c",
                    is_locked=is_graded,
                    grade_status="graded" if is_graded else "submitted",
                    grade_score=[92, 85, 78][i] if is_graded else None,
                    grade_feedback=[
                        "Чудово! Код чистий, компілюється без попереджень.",
                        "Добра робота. Додай обробку помилок вводу.",
                        "Правильно, але можна оптимізувати через do-while.",
                    ][i] if is_graded else None,
                ))
                sub_count += 1

            print(f"  📤 Submissions: +{sub_count} new")

            # ── grades ────────────────────────────────────────────────
            grade_count = 0
            for i, asgn in enumerate(all_assignments[:3]):
                r = await session.execute(
                    select(Grade).where(
                        Grade.student_id == student.id,
                        Grade.assignment_id == asgn.id,
                    ))
                if r.scalar_one_or_none():
                    continue
                session.add(Grade(
                    student_id=student.id,
                    assignment_id=asgn.id,
                    score=[92, 85, 78][i],
                    feedback=[
                        "Чудово! Код чистий, компілюється без попереджень.",
                        "Добра робота. Додай обробку помилок вводу.",
                        "Правильно, але можна оптимізувати.",
                    ][i],
                ))
                grade_count += 1

            print(f"  ⭐ Grades: +{grade_count} new")

    print()
    print("✅ Курс «Мова C» успішно створено!")
    print(f"   Курс:        {COURSE['title']}")
    print(f"   Дисципліни:  {len(DISCIPLINES)}")
    print(f"   Теми:        {sum(len(v) for v in TOPICS.values())}")
    print(f"   Завдання:    {sum(len(v) for v in ASSIGNMENTS.values())}")
    print()


if __name__ == "__main__":
    asyncio.run(seed())
