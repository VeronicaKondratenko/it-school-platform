# IT School LMS — Запуск

## Два launcher-и

| Файл | Що робить |
|------|-----------|
| **setup-and-start (Windows).bat** / **setup-and-start (Mac-Linux).sh** | ПЕРШИЙ запуск / повне перестворення: створює .venv, ставить залежності, перевіряє `backend/.env`, наповнює базу реалістичними даними (`backend.seed_realistic`) і запускає бекенд + фронтенд. |
| **start (Windows).bat** / **start (Mac-Linux).sh** | ЛИШЕ запуск уже налаштованої системи (без встановлення та без наповнення). |

> ⚠️ `setup-and-start` **видаляє** всі наявні курси й користувачів, КРІМ тестових
> акаунтів (`admin@school.com`, `teacher@example.com`, `student@example.com`).

## Перед першим запуском
1. Встановіть Python 3.10+ та PostgreSQL (запущений).
2. Створіть базу: `CREATE DATABASE it_school_db;`
3. Налаштування БД візьмуться з `backend/.env`. Якщо файлу немає, `setup-and-start`
   створить його з `backend/.env.example` і попросить вписати `DATABASE_URL` і `SECRET_KEY`.

## Перший запуск
- Windows: двічі клікніть **setup-and-start (Windows).bat**
- Mac/Linux:
  ```bash
  chmod +x "setup-and-start (Mac-Linux).sh"
  ./"setup-and-start (Mac-Linux).sh"
  ```
Після завершення відкриється браузер на `http://localhost:8080/index.html`.

## Наступні запуски
- Windows: **start (Windows).bat**
- Mac/Linux: `./"start (Mac-Linux).sh"`

## Дані для входу
Повна таблиця акаунтів — `accounts.xlsx` (і `backend/accounts.csv` після наповнення).
Паролі всіх нових акаунтів — `password`. Приклади:
- викладач: `teacher1@example.com` / `password`
- студент: `1student@example.com` / `password`
- тестові: `admin@school.com / admin123`, `teacher@example.com / password`, `student@example.com / password`

## Ручний запуск (без launcher-ів)
```bash
# 1) налаштування
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
# 2) наповнення (з кореня проєкту)
python backend/seed_realistic.py
# 3) бекенд
cd backend && uvicorn app.main:app --reload --port 8000
# 4) фронтенд (інший термінал, з кореня)
cd frontend && python -m http.server 8080
```
Режим фронтенду: у `frontend/config.js` має бути `DEMO_MODE = false`.
