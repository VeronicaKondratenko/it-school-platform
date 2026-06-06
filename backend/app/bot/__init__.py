import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher, types
from ..config import settings
from .handlers import router
import logging

logger = logging.getLogger(__name__)

bot: Bot | None = None
dp: Dispatcher | None = None
polling_task: asyncio.Task | None = None
bot_transport_mode: str = "stopped"


def _normalized_bot_mode() -> str:
    mode = (settings.BOT_MODE or "auto").strip().lower()
    if mode not in {"auto", "webhook", "polling"}:
        print(f"WARNING: Invalid BOT_MODE={settings.BOT_MODE!r}; falling back to auto")
        return "auto"
    return mode


async def init_bot():
    """Initialize bot and dispatcher (called once at startup)."""
    global bot, dp
    logger.info("Initializing Telegram bot (token loaded: %s)", bool(settings.TELEGRAM_BOT_TOKEN))
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    # Set bot commands menu
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Запустити бота"),
        types.BotCommand(command="week", description="Розклад на 7 днів"),
        types.BotCommand(command="attendance", description="Розклад на 7 днів"),
        types.BotCommand(command="checkin", description="Відмітка відвідування"),
        types.BotCommand(command="ask", description="Запитати AI (/ask текст)"),
        types.BotCommand(command="link", description="Прив'язати акаунт")
    ])

    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Telegram dispatcher initialized")


async def setup_webhook():
    """Set Telegram webhook and delete polling updates."""
    if not bot or not settings.TELEGRAM_WEBHOOK_URL:
        return
    
    # Delete any pending updates from polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Set new webhook
    await bot.set_webhook(
        url=settings.TELEGRAM_WEBHOOK_URL,
        secret_token=settings.TELEGRAM_WEBHOOK_SECRET or None,
    )
    print(f"Telegram webhook set to {settings.TELEGRAM_WEBHOOK_URL}")


async def start_polling():
    """Run dispatcher polling in the background."""
    if not bot or not dp:
        raise RuntimeError("Bot or dispatcher is not initialized")

    await bot.delete_webhook(drop_pending_updates=True)
    print("Webhook removed. Starting polling mode...")
    await dp.start_polling(bot)


async def startup_bot():
    """Called from lifespan startup."""
    global polling_task, bot_transport_mode

    print("startup_bot() called")
    try:
        await init_bot()
        print("init_bot() completed successfully")
    except Exception as e:
        print(f"ERROR: init_bot() failed: {e}")
        bot_transport_mode = "stopped"
        return
    
    bot_mode = _normalized_bot_mode()
    print(f"Telegram bot mode: {bot_mode}")

    # Force polling mode when requested.
    if bot_mode == "polling":
        print("Polling mode forced by BOT_MODE")
        bot_transport_mode = "polling"
        polling_task = asyncio.create_task(start_polling())
        return

    # Set up webhook if configured, otherwise fall back to polling in auto mode.
    if settings.TELEGRAM_WEBHOOK_URL:
        print(f"Setting webhook to: {settings.TELEGRAM_WEBHOOK_URL}")
        try:
            await setup_webhook()
            bot_transport_mode = "webhook"
            print("Webhook setup completed")
        except Exception as e:
            print(f"ERROR: setup_webhook() failed: {e}")
            if bot_mode == "auto":
                # Automatic fallback path: no additional webhook/polling env values are required.
                print("Falling back to polling mode...")
                bot_transport_mode = "polling"
                polling_task = asyncio.create_task(start_polling())
            else:
                raise
    else:
        print("Telegram bot initialized (Polling mode - no TELEGRAM_WEBHOOK_URL set)")
        bot_transport_mode = "polling"
        polling_task = asyncio.create_task(start_polling())


async def shutdown_bot():
    """Called from lifespan shutdown."""
    global bot, dp, polling_task, bot_transport_mode

    if polling_task and not polling_task.done():
        polling_task.cancel()
        with suppress(asyncio.CancelledError):
            await polling_task

    if bot:
        if bot_transport_mode == "webhook":
            await bot.delete_webhook(drop_pending_updates=False)
        await bot.session.close()
    bot_transport_mode = "stopped"
    print("Telegram bot stopped")
