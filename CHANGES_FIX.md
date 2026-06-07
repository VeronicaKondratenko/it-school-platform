# Виправлення: розкладка сторінки «Питання» + надійність Telegram-бота

## 1. Баг розкладки на `frontend/questions.html`

**Симптом.** Контент (форма «Нове питання») заїжджав під фіксований лівий
сайдбар, заголовок «Питання та звернення» був обрізаний зліва.

**Причина.** `questions.html` використовує розмітку `main-wrap → page-banner →
page-body` (як робочі сторінки `courses.html`, `grades.html` тощо). Але ті
сторінки описують ці класи **інлайн** у власному `<style>`, а `questions.html`
покладається на спільний `questions-ui.css`, у якому для темної теми був
описаний лише клас `.main` (`margin-left:260px`), а `.main-wrap`,
`.page-banner`, `.page-body` — ні. Тому контент не отримував лівого відступу під
сайдбар.

**Виправлення.** Файл `frontend/questions-ui.css`:
- додано правила `.q-page .main-wrap`, `.q-page .page-banner`,
  `.q-page .page-banner::before/h1/p`, `.q-page .page-body` (темна тема),
  що дзеркалять перевірені інлайн-стилі робочих сторінок;
- додано світлу тему для `.main-wrap` і банера;
- у медіазапиті `max-width:1024px` обнулено `margin-left` для `.main-wrap`
  і зменшено падінги банера/тіла, щоб на вузьких екранах не виникало проблеми.

Сусідні `teacher-questions.html` і `admin-questions.html` використовують
`class="main"` і вже працювали коректно — їх не чіпали.

## 2. Надійність Telegram-бота

**Контекст.** Самі хендлери (`backend/app/bot/handlers.py`) робочі: fallback на
невідомі повідомлення/кнопки вже є. Проблема — у старті/конфігурації, через що
бот «лягав» тихо.

**Виправлення.** Файл `backend/app/bot/__init__.py`:
- `init_bot()` бере токен через `.strip()` і, якщо токен порожній, кидає
  зрозумілу помилку замість падіння на `set_my_commands`;
- виклик `set_my_commands` загорнуто в `try/except` — тимчасовий збій меню
  команд більше не вбиває весь бот;
- `startup_bot()`: режим `BOT_MODE=webhook` без `TELEGRAM_WEBHOOK_URL` тепер дає
  явну помилку в лог замість тихого переходу в polling (на «сплячому» Render це
  виглядало як мертвий бот);
- `setup_webhook()` бере URL і secret через `.strip()`.

Файл `render.yaml`: додано коментар-інструкцію, як увімкнути бота в надійному
**webhook**-режимі (значення за замовчуванням лишились безпечними — бот вимкнено).

### Як надійно увімкнути бота на Render (free)
У Render → backend service → Environment виставити:

```
ENABLE_BOT=true
BOT_MODE=webhook
TELEGRAM_BOT_TOKEN=<токен від @BotFather>
TELEGRAM_WEBHOOK_URL=https://<ваш-backend>.onrender.com/api/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=<довгий випадковий рядок>
```

Polling на безкоштовному тарифі ненадійний — сервіс засинає і бот «вмирає».
Webhook — правильний вибір для Render.

### Діагностика (підставити свій токен)
```
# стан вебхука: покаже last_error_message і pending_update_count
https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# скинути застарілий вебхук і чергу (за потреби чистого старту)
https://api.telegram.org/bot<TOKEN>/deleteWebhook?drop_pending_updates=true
```

## Змінені файли
- `frontend/questions-ui.css`
- `backend/app/bot/__init__.py`
- `render.yaml`
- `CHANGES_FIX.md` (цей файл)

---

# Раунд 2: дзвіночок сповіщень + помилка надсилання питання

## 3. Прибрано плаваючий дзвіночок «!» (правий верхній кут)
Файл `frontend/api.js`: функція `initGlobalNotificationsBell()` більше не створює
кнопку. Тепер вона лише прибирає кнопку/таймер, якщо вони лишилися від старої
кешованої версії. Дзвіночок на сторінці питань вів сам на себе й не давав користі.

## 4. Питання не надсилалося («якась помилка», не з'являлось в історії)
**Причина.** `/api/student/courses` (наповнює список курсів) бере групи студента
**без** фільтра `is_active`, а перевірка при створенні питання
(`_student_group_for_course`) вимагала `StudyGroup.is_active == True`. Курс було
видно у списку, але надсилання падало з `403 You are not enrolled in this course`,
тож тред не зберігався і не з'являвся в історії.

**Виправлення.**
- `backend/app/api/endpoints/questions.py`: `_student_group_for_course` більше не
  вимагає `is_active` — бере будь-яку групу студента з цим курсом, віддаючи
  перевагу активній (узгоджено зі списком курсів). Повідомлення про помилки
  створення питання перекладено зрозумілою українською.
- `frontend/questions.html`: додано м'яку валідацію (тема й текст ≥ 3 символів,
  як вимагає бекенд) і обов'язковий вибір курсу для питання викладачу; дрібний
  збій оновлення UI після успішного збереження більше не показується як «помилка
  надсилання».

## Змінені файли (раунд 2)
- `frontend/api.js`
- `backend/app/api/endpoints/questions.py`
- `frontend/questions.html`
