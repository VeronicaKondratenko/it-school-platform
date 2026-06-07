"""Telegram bot lifecycle for IT School.

This module is intentionally defensive because the same project can run in two modes:
- local development: BOT_MODE=polling;
- Render/production: BOT_MODE=webhook.

Important production fix:
Do NOT delete the webhook on shutdown by default. During Render deploys the old
instance can shut down after the new one has configured the webhook, and deleting
it on shutdown makes the bot look completely dead.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from aiogram import Bot, Dispatcher, types

from ..config import settings
from .handlers import router

logger = logging.getLogger(__name__)

bot: Bot | None = None
dp: Dispatcher | None = None
polling_task: asyncio.Task | None = None
bot_transport_mode: str = "stopped"

_runtime: dict[str, Any] = {
    "enabled": False,
    "mode": "disabled",
    "transport": "stopped",
    "started_at": None,
    "last_error": None,
    "bot_username": None,
    "expected_webhook_url": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_last_error(message: str | None) -> None:
    _runtime["last_error"] = message
    if message:
        logger.error(message)


def _normalized_bot_mode() -> str:
    mode = (settings.BOT_MODE or "auto").strip().lower()
    if mode in {"disabled", "off", "false", "0", "no"}:
        return "disabled"
    if mode not in {"auto", "webhook", "polling"}:
        logger.warning("Invalid BOT_MODE=%r; falling back to auto", settings.BOT_MODE)
        return "auto"
    return mode


def get_bot_runtime_status() -> dict[str, Any]:
    """Return safe diagnostic info without exposing the Telegram token."""
    return {
        "enabled_setting": bool(settings.ENABLE_BOT),
        "token_configured": bool((settings.TELEGRAM_BOT_TOKEN or "").strip()),
        "mode_setting": settings.BOT_MODE,
        "normalized_mode": _normalized_bot_mode(),
        "transport": bot_transport_mode,
        "bot_initialized": bot is not None,
        "dispatcher_initialized": dp is not None,
        "polling_task_running": bool(polling_task and not polling_task.done()),
        "expected_webhook_url": (settings.TELEGRAM_WEBHOOK_URL or "").strip() or None,
        "webhook_secret_configured": bool((settings.TELEGRAM_WEBHOOK_SECRET or "").strip()),
        "delete_webhook_on_shutdown": bool(settings.TELEGRAM_DELETE_WEBHOOK_ON_SHUTDOWN),
        "runtime": dict(_runtime),
    }


async def get_webhook_info_safe() -> dict[str, Any] | None:
    """Read Telegram webhook status. Returns None when bot is not initialized."""
    if not bot:
        return None
    info = await bot.get_webhook_info()
    return {
        "url": info.url,
        "has_custom_certificate": getattr(info, "has_custom_certificate", None),
        "pending_update_count": info.pending_update_count,
        "last_error_date": getattr(info, "last_error_date", None),
        "last_error_message": info.last_error_message,
        "max_connections": getattr(info, "max_connections", None),
        "allowed_updates": getattr(info, "allowed_updates", None),
    }


async def init_bot() -> None:
    """Initialize bot and dispatcher. Called once at API startup."""
    global bot, dp

    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty; set it to enable the bot")

    logger.info("Initializing Telegram bot (token loaded: %s)", bool(token))
    bot = Bot(token=token)

    try:
        me = await bot.get_me()
        _runtime["bot_username"] = me.username
        logger.info("Telegram bot authenticated as @%s", me.username)
    except Exception as exc:
        # Invalid token or Telegram connectivity issue. This is fatal for the bot,
        # but the API can still continue running.
        raise RuntimeError(f"Telegram getMe failed: {exc}") from exc

    # Set command menu. A failure here is non-fatal.
    try:
        await bot.set_my_commands([
            types.BotCommand(command="start", description="Запустити бота"),
            types.BotCommand(command="week", description="Розклад на 7 днів"),
            types.BotCommand(command="attendance", description="Розклад на 7 днів"),
            types.BotCommand(command="checkin", description="Відмітка відвідування"),
            types.BotCommand(command="ask", description="Запитати AI (/ask текст)"),
            types.BotCommand(command="link", description="Прив'язати акаунт"),
        ])
    except Exception as exc:
        logger.warning("Could not set bot commands menu (non-fatal): %s", exc)

    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Telegram dispatcher initialized")


async def setup_webhook() -> dict[str, Any] | None:
    """Configure Telegram webhook and return Telegram's webhook info."""
    webhook_url = (settings.TELEGRAM_WEBHOOK_URL or "").strip()
    if not bot:
        raise RuntimeError("Bot is not initialized")
    if not webhook_url:
        raise RuntimeError("TELEGRAM_WEBHOOK_URL is empty")

    # Stop previous polling/webhook config and drop stale updates so Telegram does
    # not replay old updates after every deploy.
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(
        url=webhook_url,
        secret_token=(settings.TELEGRAM_WEBHOOK_SECRET or "").strip() or None,
        drop_pending_updates=True,
    )

    _runtime["expected_webhook_url"] = webhook_url
    logger.info("Telegram webhook set to %s", webhook_url)

    info = await get_webhook_info_safe()
    logger.info("Telegram webhook info: %s", info)
    return info


async def start_polling() -> None:
    """Run dispatcher polling in the background."""
    if not bot or not dp:
        raise RuntimeError("Bot or dispatcher is not initialized")

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook removed. Starting polling mode...")
    await dp.start_polling(bot)


async def startup_bot() -> None:
    """Called from FastAPI lifespan startup."""
    global polling_task, bot_transport_mode

    _runtime["enabled"] = bool(settings.ENABLE_BOT)
    _runtime["mode"] = settings.BOT_MODE
    _runtime["started_at"] = _now_iso()
    _runtime["expected_webhook_url"] = (settings.TELEGRAM_WEBHOOK_URL or "").strip() or None
    _set_last_error(None)

    logger.info("startup_bot() called")

    mode = _normalized_bot_mode()
    if not settings.ENABLE_BOT or mode == "disabled":
        bot_transport_mode = "stopped"
        _runtime["transport"] = bot_transport_mode
        logger.info("Telegram bot disabled by settings")
        return

    try:
        await init_bot()
    except Exception as exc:
        bot_transport_mode = "stopped"
        _runtime["transport"] = bot_transport_mode
        _set_last_error(f"init_bot() failed: {exc}")
        return

    webhook_url = (settings.TELEGRAM_WEBHOOK_URL or "").strip()
    logger.info("Telegram bot mode: %s", mode)

    if mode == "polling":
        bot_transport_mode = "polling"
        _runtime["transport"] = bot_transport_mode
        polling_task = asyncio.create_task(start_polling())
        logger.info("Polling mode started")
        return

    if mode == "webhook" and not webhook_url:
        bot_transport_mode = "stopped"
        _runtime["transport"] = bot_transport_mode
        _set_last_error(
            "BOT_MODE=webhook but TELEGRAM_WEBHOOK_URL is empty. "
            "Set TELEGRAM_WEBHOOK_URL=https://<backend-host>/api/webhook/telegram"
        )
        return

    if webhook_url:
        try:
            await setup_webhook()
            bot_transport_mode = "webhook"
            _runtime["transport"] = bot_transport_mode
            logger.info("Webhook mode started")
            return
        except Exception as exc:
            _set_last_error(f"setup_webhook() failed: {exc}")
            if mode != "auto":
                bot_transport_mode = "stopped"
                _runtime["transport"] = bot_transport_mode
                return
            logger.warning("Falling back to polling mode because BOT_MODE=auto")

    # auto mode without webhook URL or failed webhook -> polling.
    bot_transport_mode = "polling"
    _runtime["transport"] = bot_transport_mode
    polling_task = asyncio.create_task(start_polling())
    logger.info("Polling mode started")


async def shutdown_bot() -> None:
    """Called from FastAPI lifespan shutdown."""
    global bot, dp, polling_task, bot_transport_mode

    if polling_task and not polling_task.done():
        polling_task.cancel()
        with suppress(asyncio.CancelledError):
            await polling_task

    if bot:
        # Production fix: do not delete the webhook by default. On Render deploys,
        # deleting the webhook during shutdown can remove the active webhook and
        # make the bot stop receiving messages.
        if bot_transport_mode == "webhook" and settings.TELEGRAM_DELETE_WEBHOOK_ON_SHUTDOWN:
            with suppress(Exception):
                await bot.delete_webhook(drop_pending_updates=False)
        with suppress(Exception):
            await bot.session.close()

    bot = None
    dp = None
    polling_task = None
    bot_transport_mode = "stopped"
    _runtime["transport"] = bot_transport_mode
    logger.info("Telegram bot stopped")
