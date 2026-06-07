"""Telegram Webhook Endpoint for receiving updates from Telegram."""

from fastapi import APIRouter, HTTPException, Request
from aiogram import types
from ...config import settings
from ... import bot as bot_module
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """
    Receive updates from Telegram Webhook.
    
    Telegram sends a JSON object representing an Update.
    We parse it and feed it to the dispatcher.
    """
    # Get bot and dp dynamically from module (they're initialized at lifespan startup)
    dp = bot_module.dp
    bot = bot_module.bot
    
    
    if not dp or not bot:
        logger.error("Telegram bot not initialized")
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    # Optional: Validate secret token if configured
    if settings.TELEGRAM_WEBHOOK_SECRET:
        token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token != settings.TELEGRAM_WEBHOOK_SECRET:
            logger.warning("Invalid webhook secret token")
            raise HTTPException(status_code=403, detail="Invalid token")
    
    # Parse incoming JSON as Telegram Update
    try:
        update_data = await request.json()
        # aiogram 3.x (pydantic v2): model_validate is the correct, robust way to
        # build an Update from raw JSON. Update(**data) fails on nested objects.
        update = types.Update.model_validate(update_data)
        logger.debug("Telegram update received: %s", update.update_id)
    except Exception as e:
        logger.warning("Invalid Telegram update format: %s", e)
        raise HTTPException(status_code=400, detail=f"Invalid update format: {str(e)}")

    # Feed update to dispatcher to handle it. A failure in a single handler must
    # NOT return a non-2xx status: Telegram would keep retrying the same update
    # and the bot would look stuck. Log it and acknowledge with 200.
    try:
        await dp.feed_update(bot, update)
        logger.debug("Telegram update processed")
    except Exception:
        logger.exception("Error processing Telegram update (acknowledged to Telegram anyway)")

    # Return 200 OK immediately (Telegram expects quick response)
    return {"ok": True}
