from aiogram import Router, types, F
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.future import select
from ..database import get_db
from ..models import User, Schedule, Attendance, AttendanceStatus, Message, MessageStatus, UserRole
from datetime import datetime, timedelta
from sqlalchemy.orm import selectinload

router = Router()


class AskFlow(StatesGroup):
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
        .options(selectinload(User.groups))
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
        [InlineKeyboardButton(text="AI", callback_data="ask_to:ai")],
        [InlineKeyboardButton(text="Викладач", callback_data="ask_to:teacher")],
        [InlineKeyboardButton(text="Адмін", callback_data="ask_to:admin")],
    ])


@router.message(F.text == "Запитати")
async def cmd_ask_menu(message: types.Message):
    await message.answer("Оберіть, кому хочете поставити запитання:", reply_markup=get_ask_recipient_kb())


@router.message(Command("ask"))
async def cmd_ask_legacy(message: types.Message, command: CommandObject = None):
    """Backward-compatible /ask command: sends directly to AI."""
    if not command or not command.args:
        await message.answer(
            "Оберіть адресата через кнопку 'Запитати' або введіть: /ask <ваше питання> (для AI)."
        )
        return

    question = command.args.strip()
    await message.answer("Думаю...")
    ai_result = await ai_service.classify_and_respond(question)
    await message.answer(ai_result["response"], reply_markup=get_main_kb())


@router.callback_query(F.data.startswith("ask_to:"))
async def cb_ask_recipient(callback: types.CallbackQuery, state: FSMContext):
    recipient = callback.data.split(":", 1)[1]
    if recipient not in {"ai", "teacher", "admin"}:
        await callback.answer("Некоректний адресат", show_alert=True)
        return

    recipient_titles = {
        "ai": "AI",
        "teacher": "Викладач",
        "admin": "Адмін",
    }
    await state.update_data(ask_recipient=recipient)
    await state.set_state(AskFlow.waiting_question)
    await callback.message.answer(f"Введіть ваше запитання для: {recipient_titles[recipient]}")
    await callback.answer()


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
        await message.answer(ai_result["response"], reply_markup=get_main_kb())
        await state.clear()
        return

    async for db in get_db():
        user = await _get_telegram_user(db, message.from_user.id)
        if not user:
            await message.answer(_telegram_link_required_text())
            await state.clear()
            break

        receiver_id = None
        role_name = "адміністратора"

        if recipient == "teacher":
            teacher_ids = [g.teacher_id for g in user.groups if g.teacher_id is not None]
            receiver_id = teacher_ids[0] if teacher_ids else None
            role_name = "викладача"
        elif recipient == "admin":
            admin_result = await db.execute(select(User).where(User.role == UserRole.admin).order_by(User.id))
            admin_user = admin_result.scalars().first()
            receiver_id = admin_user.id if admin_user else None
            role_name = "адміністратора"

        msg = Message(
            sender_id=user.id,
            receiver_id=receiver_id,
            content=question,
            status=MessageStatus.pending,
            is_escalated=True,
        )
        db.add(msg)
        await db.commit()

        await message.answer(
            f"Запитання відправлено до {role_name}. Очікуйте відповідь у боті.",
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

