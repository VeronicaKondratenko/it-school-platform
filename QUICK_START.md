# QUICK START

One-click startup for the IT School project (FastAPI + HTML frontend).

## 1. Configure environment variables

1. Copy `backend/.env.example` to `backend/.env`.
2. Update values in `backend/.env`:
   - `DATABASE_URL`
   - `SECRET_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `GEMINI_API_KEY`
   - `BOT_MODE`
   - optional: `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_SECRET`

Example `DATABASE_URL`:

```text
postgresql+asyncpg://postgres:password@localhost:5432/it_school_db
```

## 2. Start project (one click)

From project root:

- Windows:

```powershell
.\start (Windows).bat
```

- Mac/Linux:

```bash
chmod +x "start (Mac-Linux).sh"
./start\ \(Mac-Linux\).sh
```

What startup script does automatically:

1. Creates `.venv` if missing
2. Installs `backend/requirements.txt`
3. Applies `alembic upgrade head`
4. Runs `python -m backend.seed` (idempotent)
5. Starts backend on `http://localhost:8000`
6. Starts frontend on first free port from `8080 -> 8081 -> 8082`
7. Opens `http://localhost:<selected_port>/index.html` in browser

Health checks:

- API: `http://localhost:8000/health`
- Swagger: `http://localhost:8000/docs`

## 3. Manual frontend fallback (optional)

If auto-start was blocked by policy/firewall, run frontend manually:

```powershell
cd frontend
python -m http.server 8080
```

## 4. Demo accounts

- student: `student@example.com` / `password`
- teacher: `teacher@example.com` / `password`
- admin: `admin@school.com` / `admin123`

## 5. Frontend mode

File: `frontend/config.js`

- `DEMO_MODE = false` -> real backend mode (recommended)
- `DEMO_MODE = true` -> local mock mode (`frontend/mockData.js`)

## 6. Telegram bot mode

File: `backend/.env`

- `BOT_MODE=auto` -> use webhook when `TELEGRAM_WEBHOOK_URL` is set, otherwise polling
- `BOT_MODE=webhook` -> force webhook mode
- `BOT_MODE=polling` -> force local polling mode

Webhook fallback behavior:

- If webhook setup fails in `BOT_MODE=auto`, the app automatically switches to polling mode.
- No additional values need to be entered for this fallback.

Recommended for local demo:

- `BOT_MODE=polling`

Recommended for public deployment:

- `BOT_MODE=webhook`

