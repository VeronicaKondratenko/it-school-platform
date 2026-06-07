from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select
from ..database import get_db
from ..models import (
    User,
    Schedule,
    Attendance,
    AttendanceStatus,
    UserRole,
    StudyGroup,
    Course,
    Discipline,
    QuestionThread,
    QuestionMessage,
    Notification,
)
from datetime import datetime, timedelta
from sqlalchemy.orm import selectinload

router = Router()


class AskFlow(StatesGroup):
    choosing_course = State()
    choosing_teacher = State()
    waiting_question = State()


WEEKDAY_UA = {
    0: "Понеділок",
    1: "Вівторок",
    2: "Середа",
    3: "Четвер",
    4: "П'ятниця",
    5: "Субота",
    6: "Неділя",
}

def get_main_kb():
    kb = [
        [KeyboardButton(text="Розклад на тиждень")],
        [KeyboardButton(text="Відмітка"), KeyboardButton(text="Запитати")],
        [KeyboardButton(text="Мій акаунт")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def _telegram_link_required_text() -> str:
    return (
        "Спочатку прив'яжіть акаунт до Telegram.\n\n"
        "Як це зробити:\n"
        "1. Увійдіть у веб-кабінет IT School.\n"
        "2. Відкрийте сторінку «Профіль».\n"
        "3. Натисніть «Підключити Telegram» або «Згенерувати код».\n"
        "4. Скопіюйте команду виду /link КОД і надішліть її сюди.\n\n"
        "Приклад: /link 123456"
    )


def _help_text(is_linked: bool = False) -> str:
    base = (
        "Я отримав ваше повідомлення. Оберіть дію кнопками нижче або використайте команду:\n\n"
        "/start — запустити бота\n"
        "/week — показати розклад на 7 днів\n"
        "/checkin — відмітити відвідування\n"
        "/ask текст — поставити питання AI\n"
        "/link КОД — прив'язати акаунт"
    )
    if not is_linked:
        return _telegram_link_required_text() + "\n\n" + base
    return base


async def _get_telegram_user(db, telegram_id: int):
    result = await db.execute(
        select(User)
        .where(User.telegram_id == telegram_id)
        .options(
            selectinload(User.groups).selectinload(StudyGroup.courses),
            selectinload(User.groups).selectinload(StudyGroup.teacher),
        )
    )
    return result.scalars().first()


async def _get_week_schedule_for_user(db, user: User):
    today = datetime.now().date()
    next_week_date = today + timedelta(days=7)
    group_ids = [g.id for g in user.groups]

    sched_result = await db.execute(
        select(Schedule)
        .where(Schedule.group_id.in_(group_ids))
        .where(Schedule.date >= today)
        .where(Schedule.date < next_week_date)
        .options(selectinload(Schedule.discipline), selectinload(Schedule.group))
        .order_by(Schedule.date, Schedule.time)
    )
    return sched_result.scalars().all()


def _format_week_schedule(schedule_items):
    response = "Ваш розклад на наступні 7 днів:\n\n"
    current_date = None

    for sched in schedule_items:
        if sched.date != current_date:
            current_date = sched.date
            day_name = WEEKDAY_UA.get(current_date.weekday(), current_date.strftime("%A"))
            response += f"\n{day_name}, {current_date.strftime('%d.%m')}\n"

        discipline_name = sched.discipline.name if sched.discipline else "Без назви предмета"
        group_name = sched.group.name if sched.group else "Група"
        link_info = f"\n     {sched.meeting_link}" if sched.meeting_link else ""
        response += (
            f"  {sched.time.strftime('%H:%M')} - {discipline_name} ({group_name})"
            f" [ID: {sched.id}]"
            f"{link_info}\n"
        )

    return response


async def _send_week_schedule(message: types.Message, db, user: User):
    if not user.groups:
        await message.answer("Ви не записані до жодної групи.")
        return

    schedule_items = await _get_week_schedule_for_user(db, user)
    if not schedule_items:
        await message.answer("На наступні 7 днів занять не заплановано.")
        return

    response = _format_week_schedule(schedule_items)
    response += "\nДля відмітки оберіть кнопку 'Відмітка'."
    await message.answer(response, reply_markup=get_main_kb())


def _make_question_title(text: str, prefix: str = "Питання з Telegram") -> str:
    clean = " ".join((text or "").split())
    if not clean:
        return prefix
    return clean[:80] if len(clean) <= 80 else clean[:77] + "..."


async def _notify(db, user_id: int | None, title: str, body: str, link: str) -> None:
    if not user_id:
        return
    db.add(Notification(user_id=user_id, title=title[:180], body=(body or "")[:1000], link=link))


async def _notify_admins(db, title: str, body: str, link: str = "/admin-questions.html") -> None:
    result = await db.execute(select(User.id).where(User.role == UserRole.admin))
    for row in result.all():
        await _notify(db, row[0], title, body, link)


def _format_teacher_name(teacher: User | None) -> str:
    if not teacher:
        return "Викладач"
    name = (teacher.full_name or teacher.email or "Викладач").strip()
    if getattr(teacher, "patronymic", None):
        name = f"{name} {teacher.patronymic}".strip()
    return name


def _add_teacher_option(entry: dict, teacher: User | None, group_name: str | None = None, source: str = "group") -> None:
    if not teacher or not getattr(teacher, "id", None):
        return
    seen = entry.setdefault("_seen_teacher_ids", set())
    if teacher.id in seen:
        return
    seen.add(teacher.id)
    label = _format_teacher_name(teacher)
    if group_name:
        label = f"{label} ({group_name})"
    entry.setdefault("teachers", []).append({
        "id": teacher.id,
        "name": _format_teacher_name(teacher),
        "label": label,
        "email": teacher.email,
        "group_name": group_name,
        "source": source,
    })


async def _get_student_question_targets(db, user: User) -> list[dict]:
    """Return courses and concrete teacher choices available for a student.

    Telegram cannot show a long web form, so the bot must guide a student step by
    step: first course, then teacher, then question text. Teachers are collected
    from the student's groups and, when available, from schedules inside the same
    group/course. This avoids the old ambiguous behaviour where the bot silently
    picked the first teacher.
    """
    options: dict[int, dict] = {}
    groups = list(user.groups or [])
    group_by_id = {g.id: g for g in groups}

    for group in groups:
        for course in list(getattr(group, "courses", []) or []):
            entry = options.setdefault(course.id, {
                "course_id": course.id,
                "course_title": course.title or f"Курс #{course.id}",
                "teachers": [],
                "_seen_teacher_ids": set(),
            })
            _add_teacher_option(entry, getattr(group, "teacher", None), group.name, "group")

    group_ids = list(group_by_id.keys())
    if group_ids:
        schedule_result = await db.execute(
            select(Schedule)
            .where(Schedule.group_id.in_(group_ids))
            .options(selectinload(Schedule.teacher), selectinload(Schedule.discipline))
        )
        for sched in schedule_result.scalars().all():
            discipline = getattr(sched, "discipline", None)
            course_id = getattr(discipline, "course_id", None)
            if not course_id or course_id not in options:
                continue
            group = group_by_id.get(sched.group_id)
            _add_teacher_option(options[course_id], getattr(sched, "teacher", None), getattr(group, "name", None), "schedule")

    result = []
    for entry in options.values():
        entry.pop("_seen_teacher_ids", None)
        entry["teachers"].sort(key=lambda t: (t.get("name") or "").lower())
        result.append(entry)
    result.sort(key=lambda x: (x.get("course_title") or "").lower())
    return result


def _find_course_option(options: list[dict], course_id: int | None) -> dict | None:
    if course_id is None:
        return None
    for item in options:
        if int(item.get("course_id")) == int(course_id):
            return item
    return None


def _find_teacher_option(course_option: dict | None, teacher_id: int | None) -> dict | None:
    if not course_option or teacher_id is None:
        return None
    for teacher in course_option.get("teachers", []):
        if int(teacher.get("id")) == int(teacher_id):
            return teacher
    return None


async def _create_bot_question_thread(db, user: User, recipient: str, question: str, course_id: int | None = None, target_user_id: int | None = None):
    """Create a structured QuestionThread from a Telegram question."""
    title = _make_question_title(question)
    target_type = recipient if recipient in {"teacher", "admin"} else "admin"
    role_name = "адміністратора"

    if target_type == "teacher":
        options = await _get_student_question_targets(db, user)
        course_option = _find_course_option(options, course_id)
        teacher_option = _find_teacher_option(course_option, target_user_id)
        if not course_option or not teacher_option:
            # Do not lose the question if the callback is stale or the student was
            # removed from a group after choosing a teacher. Route to admin with a
            # clear category, so the admin can reassign it from the web panel.
            target_type = "admin"
            target_user_id = None
            course_id = course_id if course_option else None
            role_name = "адміністратора (викладача не вдалося визначити)"
        else:
            target_user_id = int(teacher_option["id"])
            course_id = int(course_option["course_id"])
            role_name = f"викладача {teacher_option.get('name') or ''}".strip()

    thread = QuestionThread(
        student_id=user.id,
        target_type=target_type,
        target_user_id=target_user_id,
        course_id=course_id,
        title=title,
        category="telegram",
        status="new",
        priority="normal",
    )
    db.add(thread)
    await db.flush()

    db.add(QuestionMessage(
        thread_id=thread.id,
        sender_id=user.id,
        sender_role="student",
        message_text=question,
        is_ai_response=False,
    ))

    if target_type == "teacher":
        await _notify(db, target_user_id, "Нове питання з Telegram", title, "/teacher-questions.html")
        await _notify_admins(db, "Нове питання студент → викладач", title, "/admin-questions.html")
    else:
        await _notify_admins(db, "Нове звернення з Telegram", title, "/admin-questions.html")

    await db.commit()
    return thread, role_name


async def _store_bot_ai_history(db, user: User, question: str, answer: str) -> None:
    """Store a Telegram AI request so admin can see it in AI-запити."""
    title = _make_question_title(question, prefix="AI-запит з Telegram")
    thread = QuestionThread(
        student_id=user.id,
        target_type="ai",
        target_user_id=None,
        course_id=None,
        title=title,
        category="telegram_ai",
        status="answered",
        priority="normal",
    )
    db.add(thread)
    await db.flush()
    db.add(QuestionMessage(
        thread_id=thread.id,
        sender_id=user.id,
        sender_role="student",
        message_text=question,
        is_ai_response=False,
    ))
    db.add(QuestionMessage(
        thread_id=thread.id,
        sender_id=None,
        sender_role="ai",
        message_text=answer,
        is_ai_response=True,
    ))
    await _notify_admins(db, "Новий AI-запит з Telegram", title, "/admin-questions.html")
    await db.commit()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Привіт! Я офіційний бот IT School.\n\n"
        "Використовуйте кнопки нижче або меню для керування навчання.",
        reply_markup=get_main_kb()
    )

    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)
        if not user:
            await message.answer(
                "Якщо ви ще не прив'язали акаунт, отримайте одноразовий код у веб-кабінеті "
                "(кнопка «Підключити Telegram») і надішліть: \n"
                "/link КОД"
            )
            break

        await _send_week_schedule(message, db, user)
        break

@router.message(Command("link"))
async def cmd_link(message: types.Message, command: CommandObject):
    """Link Telegram account using a one-time code from the web profile.

    Important fixes:
    - the code is normalized, so `/link 123 456` or `/link 123-456` is accepted;
    - the bot checks the code in several steps and tells the real reason;
    - the same Telegram account is detached from any previous user before linking;
    - date comparison is made with naive UTC values to avoid timezone mismatch errors.
    """
    if not command.args:
        return await message.answer(
            "Щоб прив'язати акаунт, у веб-кабінеті натисніть «Підключити Telegram», "
            "отримайте одноразовий код і надішліть: /link КОД\n\n"
            "Приклад: /link 123456"
        )

    import hashlib, datetime as _dt
    from ..models import TelegramLinkCode

    raw_code = command.args.strip()
    # The web app generates a 6-digit numeric code. We accept accidental spaces/dashes.
    code = "".join(ch for ch in raw_code if ch.isdigit())
    if len(code) != 6:
        return await message.answer(
            "Код має складатися з 6 цифр. Згенеруйте новий код у веб-кабінеті та надішліть його так:\n"
            "/link 123456"
        )

    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    now = _dt.datetime.utcnow()

    async for db in get_db():
        # First find the code only by hash. Do not filter used/expired here,
        # otherwise every case looks like the same vague "expired" error.
        result = await db.execute(
            select(TelegramLinkCode)
            .where(TelegramLinkCode.code_hash == code_hash)
            .options(selectinload(TelegramLinkCode.user).selectinload(User.groups))
        )
        link = result.scalars().first()

        if not link:
            return await message.answer(
                "Код не знайдено. Перевірте, що ви ввели саме останній код із веб-кабінету.\n\n"
                "Також переконайтесь, що сайт і бот підключені до однієї бази даних."
            )

        if link.used_at is not None:
            return await message.answer(
                "Цей код уже був використаний або скасований новим кодом. "
                "Згенеруйте новий код у веб-кабінеті та введіть саме його."
            )

        expires_at = link.expires_at
        if expires_at and expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(_dt.timezone.utc).replace(tzinfo=None)

        if expires_at is not None and expires_at <= now:
            return await message.answer(
                "Код застарів. Згенеруйте новий код у веб-кабінеті та введіть його протягом часу дії."
            )

        if not link.user:
            return await message.answer(
                "Користувача для цього коду не знайдено. Згенеруйте новий код у веб-кабінеті."
            )

        user = link.user

        # One Telegram chat should belong to only one web account.
        old_owner_result = await db.execute(
            select(User).where(User.telegram_id == message.from_user.id, User.id != user.id)
        )
        for old_owner in old_owner_result.scalars().all():
            old_owner.telegram_id = None

        user.telegram_id = message.from_user.id
        link.used_at = now
        await db.commit()

        await message.answer(
            f"Акаунт {user.email} успішно прив'язано!",
            reply_markup=get_main_kb()
        )

        # Immediately show student-specific weekly schedule after successful link.
        await _send_week_schedule(message, db, user)
        break

@router.message(Command("attendance"))
async def cmd_attendance_legacy(message: types.Message):
    """Legacy command kept for backward compatibility; now shows weekly schedule."""
    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)

        if not user:
            await message.answer(_telegram_link_required_text())
            break

        await _send_week_schedule(message, db, user)
        break

@router.message(F.text == "Розклад на тиждень")
@router.message(Command("week"))
async def cmd_week_schedule(message: types.Message):
    """Get 7-day schedule for the student's groups"""
    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)

        if not user:
            await message.answer(_telegram_link_required_text())
            break

        await _send_week_schedule(message, db, user)
        break

@router.message(F.text == "Відмітка")
@router.message(Command("checkin"))
async def cmd_checkin(message: types.Message, command: CommandObject = None):
    """Interactive attendance flow: choose class, then status."""
    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)

        if not user:
            await message.answer(_telegram_link_required_text())
            break

        if not user.groups:
            await message.answer("Ви не записані до жодної групи.")
            break

        group_ids = [g.id for g in user.groups]
        today = datetime.now().date()

        # If command includes a schedule id, immediately ask for status for that lesson.
        if command and command.args:
            try:
                schedule_id = int(command.args.strip())
            except ValueError:
                await message.answer("Некоректний ID заняття. Використовуйте число.")
                break

            schedule_result = await db.execute(
                select(Schedule)
                .where(Schedule.id == schedule_id)
                .where(Schedule.group_id.in_(group_ids))
                .options(selectinload(Schedule.discipline))
            )
            schedule_item = schedule_result.scalars().first()
            if not schedule_item:
                await message.answer("Заняття не знайдено або воно не належить вашій групі.")
                break

            discipline_name = schedule_item.discipline.name if schedule_item.discipline else "Предмет"
            status_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Присутній", callback_data=f"att_status:{schedule_id}:present")],
                [InlineKeyboardButton(text="Спізнився", callback_data=f"att_status:{schedule_id}:late")],
                [InlineKeyboardButton(text="Відсутній", callback_data=f"att_status:{schedule_id}:absent")],
            ])
            await message.answer(
                f"Оберіть статус для '{discipline_name}' ({schedule_item.date.strftime('%d.%m')} {schedule_item.time.strftime('%H:%M')}):",
                reply_markup=status_kb,
            )
            break

        sched_result = await db.execute(
            select(Schedule)
            .where(Schedule.group_id.in_(group_ids))
            .where(Schedule.date >= today)
            .where(Schedule.date < today + timedelta(days=7))
            .options(selectinload(Schedule.discipline), selectinload(Schedule.group))
            .order_by(Schedule.date, Schedule.time)
        )
        schedule_items = sched_result.scalars().all()

        if not schedule_items:
            await message.answer("На наступні 7 днів занять не заплановано.")
            break

        buttons = []
        for sched in schedule_items[:12]:
            discipline_name = sched.discipline.name if sched.discipline else "Предмет"
            button_label = f"{sched.date.strftime('%d.%m')} {sched.time.strftime('%H:%M')} - {discipline_name}"
            buttons.append([
                InlineKeyboardButton(text=button_label[:64], callback_data=f"att_pick:{sched.id}")
            ])

        pick_kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Оберіть предмет/заняття для відмітки:", reply_markup=pick_kb)
        break

@router.callback_query(F.data.startswith("att_pick:"))
async def cb_pick_attendance_schedule(callback: types.CallbackQuery):
    schedule_id_str = callback.data.split(":", 1)[1]
    try:
        schedule_id = int(schedule_id_str)
    except ValueError:
        await callback.answer("Помилка ID", show_alert=True)
        return

    async for db in get_db():
        user = await _get_telegram_user(db, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку прив'яжіть акаунт", show_alert=True)
            break

        group_ids = [g.id for g in user.groups]
        schedule_result = await db.execute(
            select(Schedule)
            .where(Schedule.id == schedule_id)
            .where(Schedule.group_id.in_(group_ids))
            .options(selectinload(Schedule.discipline))
        )
        schedule_item = schedule_result.scalars().first()
        if not schedule_item:
            await callback.answer("Заняття недоступне", show_alert=True)
            break

        discipline_name = schedule_item.discipline.name if schedule_item.discipline else "Предмет"
        status_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Присутній", callback_data=f"att_status:{schedule_id}:present")],
            [InlineKeyboardButton(text="Спізнився", callback_data=f"att_status:{schedule_id}:late")],
            [InlineKeyboardButton(text="Відсутній", callback_data=f"att_status:{schedule_id}:absent")],
        ])
        await callback.message.answer(
            f"Оберіть статус для '{discipline_name}' ({schedule_item.date.strftime('%d.%m')} {schedule_item.time.strftime('%H:%M')}):",
            reply_markup=status_kb,
        )
        await callback.answer()
        break


@router.callback_query(F.data.startswith("att_status:"))
async def cb_save_attendance_status(callback: types.CallbackQuery):
    payload = callback.data.split(":")
    if len(payload) != 3:
        await callback.answer("Некоректні дані", show_alert=True)
        return

    _, schedule_id_str, status_raw = payload
    try:
        schedule_id = int(schedule_id_str)
        status_enum = AttendanceStatus(status_raw)
    except ValueError:
        await callback.answer("Некоректний статус/ID", show_alert=True)
        return

    async for db in get_db():
        user = await _get_telegram_user(db, callback.from_user.id)
        if not user:
            await callback.answer("Спочатку прив'яжіть акаунт", show_alert=True)
            break

        group_ids = [g.id for g in user.groups]
        schedule_result = await db.execute(
            select(Schedule)
            .where(Schedule.id == schedule_id)
            .where(Schedule.group_id.in_(group_ids))
        )
        schedule_item = schedule_result.scalars().first()
        if not schedule_item:
            await callback.answer("Заняття недоступне", show_alert=True)
            break

        attendance_result = await db.execute(
            select(Attendance).where(
                Attendance.student_id == user.id,
                Attendance.schedule_id == schedule_id,
            )
        )
        attendance_record = attendance_result.scalars().first()

        if attendance_record:
            attendance_record.status = status_enum
        else:
            attendance_record = Attendance(
                student_id=user.id,
                schedule_id=schedule_id,
                status=status_enum,
            )
            db.add(attendance_record)

        await db.commit()

        status_text = {
            AttendanceStatus.present: "Присутній",
            AttendanceStatus.late: "Спізнився",
            AttendanceStatus.absent: "Відсутній",
        }.get(status_enum, status_enum.value)

        await callback.message.answer(
            f"Готово! Відмітку збережено: {status_text}",
            reply_markup=get_main_kb(),
        )
        await callback.answer("Збережено")
        break

@router.message(F.text == "Мій акаунт")
async def cmd_profile(message: types.Message):
    async for db in get_db():
        result = await db.execute(select(User).where(User.telegram_id == message.from_user.id))
        user = result.scalars().first()
        if not user:
            return await message.answer("Акаунт не прив'язано.")
        
        await message.answer(
            f"**Ваш профіль**\n\n"
            f"Ім'я: {user.full_name}\n"
            f"Email: {user.email}\n"
            f"Роль: {user.role.value}\n",
            parse_mode="Markdown"
        )
        break

from ..services.ai_service import ai_service

def get_ask_recipient_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="AI-асистент", callback_data="ask_to:ai")],
        [InlineKeyboardButton(text="Викладач", callback_data="ask_to:teacher")],
        [InlineKeyboardButton(text="Адміністратор", callback_data="ask_to:admin")],
    ])


def _courses_kb(options: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in options[:20]:
        title = item.get("course_title") or f"Курс #{item.get('course_id')}"
        teachers_count = len(item.get("teachers", []))
        label = f"{title}"
        if teachers_count:
            label += f" · викладачів: {teachers_count}"
        rows.append([InlineKeyboardButton(text=label[:64], callback_data=f"ask_course:{item['course_id']}")])
    rows.append([InlineKeyboardButton(text="Написати адміністратору", callback_data="ask_to:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _teachers_kb(course_option: dict) -> InlineKeyboardMarkup:
    rows = []
    for teacher in course_option.get("teachers", [])[:20]:
        rows.append([InlineKeyboardButton(text=(teacher.get("label") or teacher.get("name") or "Викладач")[:64], callback_data=f"ask_teacher:{teacher['id']}")])
    rows.append([InlineKeyboardButton(text="Назад до вибору курсу", callback_data="ask_back:courses")])
    rows.append([InlineKeyboardButton(text="Написати адміністратору", callback_data="ask_to:admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == "Запитати")
async def cmd_ask_menu(message: types.Message):
    await message.answer(
        "Оберіть адресата. Якщо питання до викладача, я спочатку попрошу обрати курс, а потім конкретного викладача.",
        reply_markup=get_ask_recipient_kb(),
    )


@router.message(Command("ask"))
async def cmd_ask_legacy(message: types.Message, command: CommandObject = None):
    """Backward-compatible /ask command: sends directly to AI."""
    if not command or not command.args:
        await message.answer(
            "Оберіть адресата через кнопку «Запитати». Для AI також можна ввести: /ask <ваше питання>."
        )
        return

    question = command.args.strip()
    await message.answer("Думаю...")
    ai_result = await ai_service.classify_and_respond(question)
    answer = ai_result["response"]
    await message.answer(answer, reply_markup=get_main_kb())

    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)
        if user:
            await _store_bot_ai_history(db, user, question, answer)
        break


@router.callback_query(F.data == "ask_back:courses")
async def cb_ask_back_courses(callback: types.CallbackQuery, state: FSMContext):
    async for db in get_db():
        user = await _get_telegram_user(db, callback.from_user.id)
        if not user:
            await callback.message.answer(_telegram_link_required_text())
            await callback.answer()
            return
        options = await _get_student_question_targets(db, user)
        if not options:
            await callback.message.answer("Для ваших курсів не знайдено викладача. Можете написати адміністратору.", reply_markup=get_ask_recipient_kb())
            await callback.answer()
            return
        await state.set_state(AskFlow.choosing_course)
        await callback.message.answer("Оберіть курс, якого стосується питання:", reply_markup=_courses_kb(options))
        await callback.answer()
        return


@router.callback_query(F.data.startswith("ask_to:"))
async def cb_ask_recipient(callback: types.CallbackQuery, state: FSMContext):
    recipient = callback.data.split(":", 1)[1]
    if recipient not in {"ai", "teacher", "admin"}:
        await callback.answer("Некоректний адресат", show_alert=True)
        return

    if recipient == "teacher":
        async for db in get_db():
            user = await _get_telegram_user(db, callback.from_user.id)
            if not user:
                await callback.message.answer(_telegram_link_required_text())
                await callback.answer()
                return
            options = await _get_student_question_targets(db, user)
            if not options:
                await callback.message.answer(
                    "Для ваших курсів не знайдено доступного викладача. Напишіть адміністратору — він передасть питання потрібній людині.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Написати адміністратору", callback_data="ask_to:admin")]]),
                )
                await callback.answer()
                return
            await state.update_data(ask_recipient="teacher", ask_course_id=None, ask_teacher_id=None)
            await state.set_state(AskFlow.choosing_course)
            await callback.message.answer("Оберіть курс, якого стосується питання:", reply_markup=_courses_kb(options))
            await callback.answer()
            return

    recipient_titles = {
        "ai": "AI-асистента",
        "admin": "адміністратора",
    }
    await state.update_data(ask_recipient=recipient, ask_course_id=None, ask_teacher_id=None)
    await state.set_state(AskFlow.waiting_question)
    await callback.message.answer(f"Введіть ваше запитання для {recipient_titles[recipient]}:")
    await callback.answer()


@router.callback_query(F.data.startswith("ask_course:"))
async def cb_ask_course(callback: types.CallbackQuery, state: FSMContext):
    try:
        course_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Некоректний курс", show_alert=True)
        return

    async for db in get_db():
        user = await _get_telegram_user(db, callback.from_user.id)
        if not user:
            await callback.message.answer(_telegram_link_required_text())
            await callback.answer()
            return
        options = await _get_student_question_targets(db, user)
        course_option = _find_course_option(options, course_id)
        if not course_option:
            await callback.message.answer("Цей курс більше недоступний для вашого акаунта. Оберіть курс ще раз.", reply_markup=_courses_kb(options) if options else get_ask_recipient_kb())
            await callback.answer()
            return
        teachers = course_option.get("teachers", [])
        if not teachers:
            await callback.message.answer("Для цього курсу не знайдено викладача. Краще надішліть звернення адміністратору.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Написати адміністратору", callback_data="ask_to:admin")]]))
            await callback.answer()
            return
        await state.update_data(ask_recipient="teacher", ask_course_id=course_id, ask_course_title=course_option.get("course_title"), ask_teacher_id=None)
        await state.set_state(AskFlow.choosing_teacher)
        await callback.message.answer(
            f"Курс: {course_option.get('course_title')}. Тепер оберіть викладача, якому адресувати питання:",
            reply_markup=_teachers_kb(course_option),
        )
        await callback.answer()
        return


@router.callback_query(F.data.startswith("ask_teacher:"))
async def cb_ask_teacher(callback: types.CallbackQuery, state: FSMContext):
    try:
        teacher_id = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer("Некоректний викладач", show_alert=True)
        return

    data = await state.get_data()
    course_id = data.get("ask_course_id")
    if not course_id:
        await callback.message.answer("Спочатку оберіть курс.", reply_markup=get_ask_recipient_kb())
        await callback.answer()
        return

    async for db in get_db():
        user = await _get_telegram_user(db, callback.from_user.id)
        if not user:
            await callback.message.answer(_telegram_link_required_text())
            await callback.answer()
            return
        options = await _get_student_question_targets(db, user)
        course_option = _find_course_option(options, int(course_id))
        teacher_option = _find_teacher_option(course_option, teacher_id)
        if not teacher_option:
            await callback.message.answer("Цей викладач недоступний для обраного курсу. Оберіть викладача ще раз.", reply_markup=_teachers_kb(course_option) if course_option else get_ask_recipient_kb())
            await callback.answer()
            return
        await state.update_data(ask_recipient="teacher", ask_course_id=int(course_id), ask_teacher_id=teacher_id, ask_teacher_name=teacher_option.get("name"))
        await state.set_state(AskFlow.waiting_question)
        await callback.message.answer(
            f"Адресат: {teacher_option.get('name')}\nКурс: {course_option.get('course_title')}\n\nТепер напишіть текст питання."
        )
        await callback.answer()
        return


@router.message(AskFlow.waiting_question)
async def on_ask_question(message: types.Message, state: FSMContext):
    question = (message.text or "").strip()
    if not question:
        await message.answer("Будь ласка, введіть текст запитання.")
        return

    data = await state.get_data()
    recipient = data.get("ask_recipient")

    if recipient == "ai":
        await message.answer("Думаю...")
        ai_result = await ai_service.classify_and_respond(question)
        answer = ai_result["response"]
        await message.answer(answer, reply_markup=get_main_kb())
        async for db in get_db():
            user = await _get_telegram_user(db, message.from_user.id)
            if user:
                await _store_bot_ai_history(db, user, question, answer)
            break
        await state.clear()
        return

    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)
        if not user:
            await message.answer(_telegram_link_required_text())
            await state.clear()
            break

        course_id = data.get("ask_course_id")
        teacher_id = data.get("ask_teacher_id")
        thread, role_name = await _create_bot_question_thread(
            db,
            user,
            recipient,
            question,
            course_id=int(course_id) if course_id else None,
            target_user_id=int(teacher_id) if teacher_id else None,
        )

        await message.answer(
            f"Запитання відправлено до {role_name}.\n"
            f"Номер звернення: #{thread.id}\n\n"
            f"Відповідь прийде у веб-кабінет, а якщо Telegram прив'язаний — також сюди.",
            reply_markup=get_main_kb(),
        )
        await state.clear()
        break

@router.message()
async def fallback_message(message: types.Message):
    """Fallback for any ordinary message that was not processed by previous handlers.

    Without this handler aiogram logs "Update is not handled" and the user gets no answer.
    The handler is intentionally placed at the end of the file so it does not intercept
    /start, /link, /week, /checkin, the ask FSM flow, or button handlers.
    """
    text = (message.text or "").strip()

    # Non-text content: photo, sticker, voice, document, etc.
    if not text:
        async for db in get_db():
            user = await _get_telegram_user(db, message.from_user.id)
            await message.answer(
                "Я отримав повідомлення, але зараз працюю тільки з текстовими командами.\n\n"
                + _help_text(is_linked=bool(user)),
                reply_markup=get_main_kb(),
            )
            break
        return

    # Unknown command.
    if text.startswith("/"):
        async for db in get_db():
            user = await _get_telegram_user(db, message.from_user.id)
            await message.answer(
                "Я не знаю такої команди.\n\n" + _help_text(is_linked=bool(user)),
                reply_markup=get_main_kb(),
            )
            break
        return

    # Plain text that is not part of an active FSM scenario.
    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)
        if not user:
            await message.answer(_help_text(is_linked=False), reply_markup=get_main_kb())
            break

        await message.answer(
            _help_text(is_linked=True),
            reply_markup=get_main_kb(),
        )
        break


@router.callback_query()
async def fallback_callback(callback: types.CallbackQuery):
    """Fallback for outdated/unknown inline buttons."""
    await callback.answer("Ця дія вже недоступна або не підтримується. Спробуйте відкрити меню знову.", show_alert=True)

