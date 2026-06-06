import os
from pydantic_settings import BaseSettings, SettingsConfigDict


# Get the directory of the current file (config.py)
# config.py is in backend/app/, so .env is at ../../.env
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(base_dir, "backend", ".env")

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    TELEGRAM_BOT_TOKEN: str = ""
    GEMINI_API_KEY: str = ""
    # Telegram bot is OFF by default so the API can start without Telegram.
    # Set ENABLE_BOT=true (and a valid token) to turn it on.
    ENABLE_BOT: bool = False
    BOT_MODE: str = "disabled"
    # Webhook settings (optional; if not set, fallback to polling)
    TELEGRAM_WEBHOOK_URL: str = ""
    TELEGRAM_WEBHOOK_SECRET: str = ""
    # Operational toggles (safe defaults for local dev; tighten in production).
    SQL_ECHO: bool = False
    AUTO_CREATE_DB: bool = True
    CORS_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=env_path if os.path.exists(env_path) else ".env",
        extra="ignore",
    )


settings = Settings()
