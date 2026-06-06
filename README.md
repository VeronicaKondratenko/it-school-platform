# IT School Platform

Web platform for an IT school with role-based dashboards for students, teachers and administrators.

## Project structure

```text
backend/   FastAPI + SQLAlchemy + PostgreSQL + Telegram bot integration
frontend/  Static HTML/CSS/JavaScript frontend
render.yaml Render Blueprint for backend + frontend + PostgreSQL
```

## Demo accounts after seeding

```text
Admin:   admin@school.com / admin123
Teacher: teacher@example.com / password
Student: student@example.com / password
```

## Local run

Use the local startup scripts:

```text
setup-and-start (Windows).bat
start (Windows).bat
```

For manual backend run:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Render publication

Read the detailed guide:

```text
PUBLICATION_GUIDE_RENDER.md
```

Short Render settings:

```text
Backend Web Service
Root Directory: backend
Build Command: pip install --upgrade pip && pip install -r requirements.txt
Start Command: python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT

Frontend Static Site
Root Directory: frontend
Build Command: echo "Static frontend - no build step"
Publish Directory: .
```

## Important security note

Never publish a real `.env` file. Use Render Environment Variables instead.
# it-school-platform
# it-school-platform
