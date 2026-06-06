# Повна інструкція публікації IT School Platform на Render

Цей проєкт підготовлений для публікації на Render. У ньому є:

- `backend/` — FastAPI backend;
- `frontend/` — статичний HTML/CSS/JS frontend;
- `render.yaml` — готовий Render Blueprint;
- `RENDER_ENV_TEMPLATE.txt` — шаблон змінних середовища;
- `backend/.env.example` — приклад локального env-файлу без секретів;
- `backend/seed_demo.py` — один скрипт для наповнення бази демо-даними.

---

## 0. Що потрібно мати перед початком

Потрібно мати:

1. Обліковий запис GitHub.
2. Обліковий запис Render.
3. Встановлений Git на Windows.
4. Проєкт із цього архіву `IT-School-RENDER-READY.zip`.
5. Бажано Visual Studio Code, але можна і без нього.

---

## 1. Розпакуй архів правильно

1. Натисни правою кнопкою по архіву `IT-School-RENDER-READY.zip`.
2. Обери `Extract All...` або `7-Zip → Extract to IT-School-RENDER-READY\`.
3. Поклади папку, наприклад, сюди:

```text
C:\Users\Твоє_імʼя\Desktop\IT-School-RENDER-READY
```

У папці має бути така структура:

```text
IT-School-RENDER-READY/
├── backend/
├── frontend/
├── render.yaml
├── RENDER_ENV_TEMPLATE.txt
├── PUBLICATION_GUIDE_RENDER.md
├── .gitignore
└── ...
```

---

## 2. Перевір, що в проєкті немає секретів

У публічний GitHub НЕ можна заливати реальний файл:

```text
backend/.env
```

У цьому архіві його не має бути. Має бути тільки:

```text
backend/.env.example
```

Також у `.gitignore` уже додано:

```gitignore
backend/.env
.env
*.env
*.db
sql_app.db
venv/
.venv/
__pycache__/
```

Це потрібно, щоб випадково не опублікувати паролі, токени Telegram, ключі Gemini або локальну базу.

---

## 3. Створи репозиторій на GitHub

1. Відкрий GitHub.
2. Натисни `+` у правому верхньому куті.
3. Обери `New repository`.
4. Заповни:

```text
Repository name: it-school-platform
Visibility: Private або Public
```

Для дипломного показу можна обрати `Private`, а Render все одно зможе отримати доступ, якщо ти дозволиш.

5. НЕ став галочку `Add a README file`, якщо завантажуєш уже готовий проєкт.
6. Натисни `Create repository`.

---

## 4. Завантаж проєкт на GitHub через Git Bash

Відкрий папку проєкту.

У порожньому місці папки натисни правою кнопкою:

```text
Open Git Bash here
```

Далі введи команди по черзі.

### 4.1. Ініціалізуй Git

```bash
git init
```

### 4.2. Додай файли

```bash
git add .
```

### 4.3. Створи перший commit

```bash
git commit -m "Initial Render-ready IT School platform"
```

### 4.4. Підключи GitHub repository

На GitHub після створення repository буде URL типу:

```text
https://github.com/your-login/it-school-platform.git
```

Скопіюй його і виконай:

```bash
git branch -M main
git remote add origin https://github.com/your-login/it-school-platform.git
git push -u origin main
```

Якщо Git попросить логін — увійди у GitHub.

---

## 5. Спосіб публікації №1 — рекомендований для новачка: вручну через Render Dashboard

Цей спосіб простіший, бо ти все бачиш у веб-інтерфейсі.

Потрібно створити 3 речі:

```text
1. PostgreSQL database
2. Backend Web Service
3. Frontend Static Site
```

---

# Частина A. Створення PostgreSQL на Render

1. Відкрий Render Dashboard.
2. Натисни `New +`.
3. Обери `PostgreSQL`.
4. Заповни:

```text
Name: it-school-db
Database: it_school
User: it_school_user
Region: Frankfurt або найближчий доступний
Plan: Free, якщо доступний
```

5. Натисни `Create Database`.
6. Дочекайся, поки база створиться.
7. Відкрий створену базу.
8. Знайди блок `Connections`.
9. Скопіюй `Internal Database URL`.

Він виглядає приблизно так:

```text
postgresql://user:password@host:5432/it_school
```

Саме його потрібно вставити у backend Environment Variables як `DATABASE_URL`.

---

# Частина B. Створення Backend Web Service

1. У Render натисни `New +`.
2. Обери `Web Service`.
3. Обери GitHub repository `it-school-platform`.
4. Якщо Render просить доступ до GitHub — дозволь доступ до цього repository.
5. Заповни поля:

```text
Name: it-school-backend
Region: Frankfurt або найближчий доступний
Branch: main
Root Directory: backend
Runtime: Python
Build Command: pip install --upgrade pip && pip install -r requirements.txt
Start Command: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
Plan: Free, якщо доступний
```

6. Перед створенням відкрий секцію `Environment Variables`.
7. Додай змінні:

```env
DATABASE_URL=встав сюди Internal Database URL з Render PostgreSQL
SECRET_KEY=довгий_секретний_ключ
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=*
ENABLE_BOT=false
BOT_MODE=disabled
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_URL=
TELEGRAM_WEBHOOK_SECRET=
GEMINI_API_KEY=
SQL_ECHO=false
AUTO_CREATE_DB=true
PYTHON_VERSION=3.11.9
```

Для `SECRET_KEY` можна згенерувати значення локально командою:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Якщо Python не встановлений, тимчасово можна написати довгий випадковий рядок без пробілів, наприклад 60+ символів.

8. Натисни `Create Web Service`.
9. Дочекайся, поки build завершиться.
10. Після успішного деплою відкрий:

```text
https://it-school-backend.onrender.com/health
```

Має бути відповідь:

```json
{"status":"ok"}
```

Також можна відкрити:

```text
https://it-school-backend.onrender.com/docs
```

Якщо відкрилась сторінка Swagger/FastAPI — backend працює.

---

# Частина C. Створення Frontend Static Site

1. У Render натисни `New +`.
2. Обери `Static Site`.
3. Обери той самий GitHub repository `it-school-platform`.
4. Заповни:

```text
Name: it-school-frontend
Branch: main
Root Directory: frontend
Build Command: echo "Static frontend - no build step"
Publish Directory: .
Plan: Free, якщо доступний
```

5. Натисни `Create Static Site`.
6. Дочекайся деплою.
7. Відкрий:

```text
https://it-school-frontend.onrender.com
```

Це головне посилання, яке можна буде дати викладачу.

---

## 6. Дуже важливо: перевір API_BASE

У файлі:

```text
frontend/config.js
```

я вже підготувала автоматичну логіку:

- локально frontend звертається до `http://localhost:8000`;
- на Render frontend звертається до `https://it-school-backend.onrender.com`.

Тому, якщо backend названий саме:

```text
it-school-backend
```

то нічого міняти не треба.

Якщо Render не дозволив таку назву і зробив іншу, наприклад:

```text
https://it-school-backend-abc1.onrender.com
```

тоді відкрий:

```text
frontend/config.js
```

і заміни рядок:

```js
const RENDER_BACKEND_URL = 'https://it-school-backend.onrender.com';
```

на реальну адресу backend.

Після зміни зроби:

```bash
git add frontend/config.js
git commit -m "Update Render backend URL"
git push
```

Render сам redeploy-не frontend.

---

## 7. Наповнення бази тестовими даними

Після першого запуску backend таблиці створяться автоматично, але база буде порожня або майже порожня. Для демонстрації потрібно запустити seed.

Найпростіший спосіб — запустити seed зі свого компʼютера, але підключити його до Render database.

### 7.1. Створи локальний `backend/.env`

У папці `backend/` створи файл:

```text
.env
```

Скопіюй туди змінні з Render, але `DATABASE_URL` краще взяти `External Database URL`, бо ти запускаєш seed зі свого компʼютера, а не всередині Render.

Приклад:

```env
DATABASE_URL=postgresql://user:password@host:5432/it_school
SECRET_KEY=будь_який_довгий_секрет
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
CORS_ORIGINS=*
ENABLE_BOT=false
BOT_MODE=disabled
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_URL=
TELEGRAM_WEBHOOK_SECRET=
GEMINI_API_KEY=
SQL_ECHO=false
AUTO_CREATE_DB=true
```

### 7.2. Встанови залежності локально

У Git Bash або PowerShell з кореня проєкту:

```bash
cd backend
python -m venv .venv
```

На Windows активуй:

```bash
.venv\Scripts\activate
```

Встанови залежності:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 7.3. Запусти demo seed

Повернись у корінь проєкту:

```bash
cd ..
```

Запусти:

```bash
python backend/seed_demo.py
```

Після виконання будуть доступні тестові акаунти:

```text
admin@school.com / admin123
teacher@example.com / password
student@example.com / password
```

---

## 8. Після seed перевір сайт

Відкрий frontend:

```text
https://it-school-frontend.onrender.com
```

Перевір по черзі:

### Студент

```text
Email: student@example.com
Password: password
```

Перевір:

- dashboard;
- курси;
- розклад;
- завдання;
- оцінки;
- профіль.

### Викладач

```text
Email: teacher@example.com
Password: password
```

Перевір:

- курси викладача;
- завдання;
- студенти;
- повідомлення;
- відвідуваність.

### Адмін

```text
Email: admin@school.com
Password: admin123
```

Перевір:

- користувачів;
- групи;
- курси;
- розклад;
- статистику.

---

## 9. Після створення frontend онови CORS

Поки backend створюється, можна було ставити:

```env
CORS_ORIGINS=*
```

Коли frontend уже має фінальну адресу, краще зробити професійно.

У backend service на Render:

1. Відкрий `Environment`.
2. Знайди `CORS_ORIGINS`.
3. Заміни `*` на:

```env
CORS_ORIGINS=https://it-school-frontend.onrender.com
```

4. Натисни `Save, rebuild, and deploy`.

Якщо frontend має іншу адресу — постав саме її.

---

## 10. Якщо хочеш увімкнути Telegram-бота на Render

Для першого показу викладачу краще залишити бота вимкненим:

```env
ENABLE_BOT=false
BOT_MODE=disabled
```

Якщо потрібно увімкнути Telegram-бота на Render, у backend Environment Variables постав:

```env
ENABLE_BOT=true
BOT_MODE=webhook
TELEGRAM_BOT_TOKEN=твій_реальний_токен
TELEGRAM_WEBHOOK_URL=https://it-school-backend.onrender.com/api/webhook/telegram
TELEGRAM_WEBHOOK_SECRET=довгий_секретний_рядок
```

Після цього натисни:

```text
Save, rebuild, and deploy
```

Якщо backend має іншу адресу, у `TELEGRAM_WEBHOOK_URL` постав її.

---

## 11. Спосіб публікації №2 — через Render Blueprint

У проєкті вже є файл:

```text
render.yaml
```

Він описує:

- backend service;
- frontend static site;
- PostgreSQL database;
- основні environment variables.

Якщо хочеш спробувати Blueprint:

1. Завантаж проєкт на GitHub.
2. У Render натисни `New +`.
3. Обери `Blueprint`.
4. Обери GitHub repository.
5. Render знайде `render.yaml`.
6. Натисни `Apply` або `Create Blueprint`.

Але для новачка я рекомендую ручний спосіб через Dashboard, бо там легше бачити кожен крок.

---

## 12. Типові помилки і що робити

### Помилка: frontend відкривається, але login не працює

Перевір:

1. Відкрий браузер → F12 → Network.
2. Подивись, куди йде запит.
3. Якщо бачиш `localhost:8000`, значить не оновився backend URL у `frontend/config.js`.
4. Якщо бачиш Render backend, але червона помилка CORS — перевір `CORS_ORIGINS` у backend Environment.

---

### Помилка: backend build failed

Перевір у Render Logs:

- чи правильний `Root Directory: backend`;
- чи правильний `Build Command`;
- чи є `requirements.txt` у `backend/`;
- чи не забула додати environment variables.

Правильні команди:

```text
Build Command: pip install --upgrade pip && pip install -r requirements.txt
Start Command: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

### Помилка: `DATABASE_URL` missing

Значить у backend service не додано змінну:

```env
DATABASE_URL=...
```

Додай її у Render → backend service → Environment.

---

### Помилка: сайт відкрився, але немає курсів/користувачів

Ймовірно, база порожня. Запусти:

```bash
python backend/seed_demo.py
```

---

### Помилка: перше відкриття сайту довге

На free plan Render backend може “засинати”. Перед демонстрацією відкрий сайт сама заздалегідь, щоб backend прокинувся.

---

## 13. Що давати викладачу

Викладачу давай не backend, а frontend-посилання:

```text
https://it-school-frontend.onrender.com
```

І тестові акаунти:

```text
Студент:
student@example.com / password

Викладач:
teacher@example.com / password

Адміністратор:
admin@school.com / admin123
```

---

## 14. Фінальний чеклист

Перед тим як надсилати посилання викладачу, перевір:

- [ ] `backend/.env` не завантажений на GitHub.
- [ ] `sql_app.db` не завантажений на GitHub.
- [ ] Backend `/health` відкривається.
- [ ] Backend `/docs` відкривається.
- [ ] Frontend відкривається.
- [ ] Login студента працює.
- [ ] Login викладача працює.
- [ ] Login адміна працює.
- [ ] У F12 → Network немає `localhost:8000`.
- [ ] У F12 → Console немає червоних помилок.
- [ ] CORS_ORIGINS встановлено на frontend URL.
- [ ] База наповнена через `python backend/seed_demo.py`.

---

## 15. Найкоротша схема

```text
1. Розпакувати IT-School-RENDER-READY.zip.
2. Завантажити папку на GitHub.
3. Render → New → PostgreSQL.
4. Render → New → Web Service → backend.
5. Додати Environment Variables.
6. Перевірити /health.
7. Render → New → Static Site → frontend.
8. Запустити python backend/seed_demo.py для демо-даних.
9. Перевірити логін трьох ролей.
10. Надіслати frontend-посилання викладачу.
```
