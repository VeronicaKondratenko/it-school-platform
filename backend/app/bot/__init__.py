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
    token = (settings.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        # Without a token any Telegram API call (e.g. set_my_commands) raises,
        # which previously aborted the whole bot startup silently.
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty; set it to enable the bot")
    logger.info("Initializing Telegram bot (token loaded: %s)", bool(token))
    bot = Bot(token=token)

    # Set bot commands menu. A transient failure here must NOT kill the bot:
    # the command menu is cosmetic, the handlers work regardless.
    try:
        await bot.set_my_commands([
            types.BotCommand(command="start", description="Запустити бота"),
            types.BotCommand(command="week", description="Розклад на 7 днів"),
            types.BotCommand(command="attendance", description="Розклад на 7 днів"),
            types.BotCommand(command="checkin", description="Відмітка відвідування"),
            types.BotCommand(command="ask", description="Запитати AI (/ask текст)"),
            types.BotCommand(command="link", description="Прив'язати акаунт")
        ])
    except Exception as e:
        logger.warning("Could not set bot commands menu (non-fatal): %s", e)

    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Telegram dispatcher initialized")


async def setup_webhook():
    """Set Telegram webhook and delete polling updates."""
    webhook_url = (settings.TELEGRAM_WEBHOOK_URL or "").strip()
    if not bot or not webhook_url:
        return

    # Delete any pending updates from polling
    await bot.delete_webhook(drop_pending_updates=True)

    # Set new webhook
    await bot.set_webhook(
        url=webhook_url,
        secret_token=(settings.TELEGRAM_WEBHOOK_SECRET or "").strip() or None,
    )
    print(f"Telegram webhook set to {webhook_url}")


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

    webhook_url = (settings.TELEGRAM_WEBHOOK_URL or "").strip()

    # Force polling mode when requested.
    if bot_mode == "polling":
        print("Polling mode forced by BOT_MODE")
        bot_transport_mode = "polling"
        polling_task = asyncio.create_task(start_polling())
        return

    # Explicit webhook mode requires a URL. Don't silently fall back to polling,
    # which on a sleeping free host looks like a dead bot.
    if bot_mode == "webhook" and not webhook_url:
        print("ERROR: BOT_MODE=webhook but TELEGRAM_WEBHOOK_URL is empty. "
              "Set TELEGRAM_WEBHOOK_URL=https://<backend-host>/api/webhook/telegram")
        bot_transport_mode = "stopped"
        return

    # Set up webhook if configured, otherwise fall back to polling in auto mode.
    if webhook_url:
        print(f"Setting webhook to: {webhook_url}")
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
