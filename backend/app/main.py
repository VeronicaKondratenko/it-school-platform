from fastapi import FastAPI, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .database import get_db, engine, Base
from . import models, schemas
from .api.endpoints import auth, courses, groups, schedule, users, chat, reports, admin, messages, student, teacher, webhook, attendance, assignments, disciplines, questions, notifications
from contextlib import asynccontextmanager
from .bot import startup_bot, shutdown_bot
from .config import settings
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _bot_enabled() -> bool:
    return settings.ENABLE_BOT and (settings.BOT_MODE or "").lower() != "disabled"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure schema is up-to-date (dev only), then optionally start the bot.
    if settings.AUTO_CREATE_DB:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    if _bot_enabled():
        try:
            await startup_bot()
            logger.info("Telegram bot started")
        except Exception:
            logger.exception("Telegram bot failed to start; continuing without it")
    else:
        logger.info("Telegram bot disabled (set ENABLE_BOT=true to enable)")

    try:
        yield
    finally:
        # Shutdown: stop the Telegram bot if it was started.
        if _bot_enabled():
            try:
                await shutdown_bot()
            except Exception:
                logger.exception("Error during Telegram bot shutdown")
        await engine.dispose()
        logger.info("Shutdown complete")

app = FastAPI(title="IT School MVP API", lifespan=lifespan)

# CORS middleware MUST be added FIRST (will execute LAST in middleware chain).
# Origins come from settings.CORS_ORIGINS ("*" for dev; comma-separated domains in prod).
_cors_origins = [o.strip() for o in (settings.CORS_ORIGINS or "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

app.include_router(auth.router,     prefix="/api/auth",     tags=["auth"])
app.include_router(courses.router,   prefix="/api/courses",   tags=["courses"])
app.include_router(disciplines.router, prefix="/api/disciplines", tags=["disciplines"])
app.include_router(groups.router,    prefix="/api/groups",    tags=["groups"])
app.include_router(schedule.router,  prefix="/api/schedule",  tags=["schedule"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["attendance"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["assignments"])
app.include_router(users.router,     prefix="/api/users",     tags=["users"])
app.include_router(chat.router,      prefix="/api/chat",      tags=["chat"])
app.include_router(reports.router,   prefix="/api/reports",   tags=["reports"])
app.include_router(admin.router,     prefix="/api/admin",     tags=["admin"])
app.include_router(messages.router,  prefix="/api/messages",  tags=["messages"])
app.include_router(student.router,   prefix="/api/student",   tags=["student"])
app.include_router(teacher.router,   prefix="/api/teacher",   tags=["teacher"])
app.include_router(webhook.router,   prefix="/api/webhook",   tags=["webhook"])
app.include_router(questions.router, prefix="/api/questions", tags=["questions"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Log validation errors in detail"""
    logger.warning("[VALIDATION ERROR] %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc.errors())}
    )

@app.get("/")
async def root():
    return {"message": "Welcome to IT School API"}

# Basic Health Check
@app.get("/health")
async def health():
    return {"status": "ok"}
