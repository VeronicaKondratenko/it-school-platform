# 🚀 Запуск IT School LMS з реальною базою даних

## Що вже зроблено
- `frontend/config.js` → `DEMO_MODE = false` ✅
- `.env` з твоїми налаштуваннями PostgreSQL вже є ✅

## Кроки запуску

### 1. Переконайся що PostgreSQL запущений і база існує
```sql
-- У psql або pgAdmin:
CREATE DATABASE it_school_db;
```

### 2. Встанови залежності (один раз)
```bash
cd html-version/backend
pip install -r requirements.txt
```

### 3. Застосуй міграції (створює таблиці)
```bash
cd html-version/backend
alembic upgrade head
```

### 4. Заповни базу тестовими даними (необов'язково, якщо дані вже є)
```bash
cd html-version
python run_seed.py
```

### 5. Запусти бекенд
```bash
cd html-version/backend
uvicorn app.main:app --reload --port 8000
```

### 6. Відкрий фронтенд
Просто відкрий `html-version/frontend/index.html` у браузері.

---

## Дані для входу (якщо запускав seed)
| Email | Пароль | Роль |
|-------|--------|------|
| admin@test.com | test123 | Адмін |
| teacher@test.com | test123 | Викладач |
| student@test.com | test123 | Студент |

## Налаштування бази (.env)
Файл: `html-version/backend/.env`
```
DATABASE_URL=postgresql+asyncpg://postgres:1111@localhost:5432/it_school_db
```
Якщо пароль або ім'я бази інші — відредагуй цей файл.

## Швидкий запуск (Windows)
Двічі клікни: `start (Windows).bat`

## Швидкий запуск (Mac/Linux)
```bash
chmod +x "start (Mac-Linux).sh"
./"start (Mac-Linux).sh"
```
