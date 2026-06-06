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
        update = types.Update(**update_data)
        logger.debug("Telegram update received: %s", update.update_id)
    except Exception as e:
        logger.warning("Invalid Telegram update format")
        raise HTTPException(status_code=400, detail=f"Invalid update format: {str(e)}")
    
    # Feed update to dispatcher to handle it
    try:
        await dp.feed_update(bot, update)
        logger.debug("Telegram update processed")
    except Exception as e:
        logger.exception("Error processing Telegram update")
        raise HTTPException(status_code=500, detail="Error processing update")
    
    # Return 200 OK immediately (Telegram expects quick response)
    return {"ok": True}
