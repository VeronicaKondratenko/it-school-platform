"""
Script to:
1. Create the 'it_school_db' PostgreSQL database
2. Create all SQLAlchemy model tables inside it
"""

import asyncio
import asyncpg
import os
import sys

# Read connection params from environment (fall back to local dev defaults).
# This keeps create_db.py consistent with backend/.env instead of a hardcoded
# password that silently drifts out of sync.
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
TARGET_DB = os.getenv("POSTGRES_DB", "it_school_db")

# ---- Step 1: Create the database ----
async def create_database():
    try:
        conn = await asyncpg.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            database="postgres"  # connect to the default DB first
        )
        # Check if DB already exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", TARGET_DB
        )
        if exists:
            print(f"OK: database '{TARGET_DB}' already exists.")
        else:
            # CREATE DATABASE requires autocommit (no transaction)
            await conn.execute(f'CREATE DATABASE "{TARGET_DB}"')
            print(f"OK: database '{TARGET_DB}' created.")
        await conn.close()
    except Exception as e:
        print(f"ERROR while creating database: {e}")
        sys.exit(1)

# ---- Step 2: Create all tables ----
async def create_tables():
    try:
        # Import here after DB is created so the connection string is correct
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from backend.app.database import engine, Base
        import backend.app.models  # noqa: F401 – registers all models with Base.metadata

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Всі таблиці успішно створені в 'it_school_db'!")
        await engine.dispose()
    except Exception as e:
        print(f"❌ Помилка під час створення таблиць: {e}")
        sys.exit(1)

async def main():
    print("Крок 1: Підключення до PostgreSQL і створення БД...")
    await create_database()
    print("\nКрок 2: Створення таблиць за моделями SQLAlchemy...")
    await create_tables()
    print("\nГотово! Тепер можна запускати бекенд.")

if __name__ == "__main__":
    asyncio.run(main())
