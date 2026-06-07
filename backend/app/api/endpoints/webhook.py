"""Telegram webhook endpoints and diagnostics."""

from __future__ import annotations

import logging

from aiogram import types
from fastapi import APIRouter, HTTPException, Request

from ... import bot as bot_module
from ...config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_admin_secret(request: Request) -> None:
    """Protect diagnostic write actions with the webhook secret when configured."""
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        return
    token = request.headers.get("X-Telegram-Bot-Api-Secret-Token") or request.headers.get("X-Admin-Secret")
    if token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid token")


@router.get("/telegram/status")
async def telegram_status():
    """Safe status endpoint. Does not expose Telegram token."""
    status = bot_module.get_bot_runtime_status()
    webhook_info = None
    try:
        webhook_info = await bot_module.get_webhook_info_safe()
    except Exception as exc:
        webhook_info = {"error": str(exc)}
    return {"ok": True, "status": status, "webhook_info": webhook_info}


@router.post("/telegram/reconfigure")
async def telegram_reconfigure(request: Request):
    """Manually re-set webhook after env changes.

    Use only when BOT_MODE=webhook and TELEGRAM_WEBHOOK_URL is configured.
    If TELEGRAM_WEBHOOK_SECRET is set, pass it in either:
    - X-Telegram-Bot-Api-Secret-Token, or
    - X-Admin-Secret.
    """
    _validate_admin_secret(request)
    if not bot_module.bot:
        raise HTTPException(status_code=503, detail="Bot is not initialized")
    if (settings.BOT_MODE or "").lower() != "webhook":
        raise HTTPException(status_code=400, detail="BOT_MODE is not webhook")
    if not settings.TELEGRAM_WEBHOOK_URL:
        raise HTTPException(status_code=400, detail="TELEGRAM_WEBHOOK_URL is empty")

    try:
        info = await bot_module.setup_webhook()
    except Exception as exc:
        logger.exception("Telegram webhook reconfigure failed")
        raise HTTPException(status_code=500, detail=f"Webhook reconfigure failed: {exc}")

    return {"ok": True, "webhook_info": info, "status": bot_module.get_bot_runtime_status()}


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram updates and feed them to aiogram dispatcher."""
    dp = bot_module.dp
    bot = bot_module.bot

    if not dp or not bot:
        logger.error("Telegram webhook called, but bot is not initialized")
        raise HTTPException(status_code=503, detail="Bot not initialized")

    if settings.TELEGRAM_WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != settings.TELEGRAM_WEBHOOK_SECRET:
            logger.warning("Invalid Telegram webhook secret token")
            raise HTTPException(status_code=403, detail="Invalid token")

    try:
        update_data = await request.json()
        # aiogram 3.x needs the bot in pydantic context for some Telegram objects.
        update = types.Update.model_validate(update_data, context={"bot": bot})
        logger.info("Telegram update received: %s", update.update_id)
    except Exception as exc:
        logger.warning("Invalid Telegram update format: %s", exc)
        raise HTTPException(status_code=400, detail=f"Invalid update format: {exc}")

    try:
        await dp.feed_update(bot, update)
        logger.info("Telegram update processed: %s", update.update_id)
    except Exception:
        # Always acknowledge Telegram with 200. Otherwise Telegram retries the same
        # bad update again and again, and the bot looks stuck.
        logger.exception("Error processing Telegram update %s; acknowledged anyway", update.update_id)

    return {"ok": True}
