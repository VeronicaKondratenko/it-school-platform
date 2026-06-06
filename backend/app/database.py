from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings


def _to_asyncpg_url(url: str) -> str:
    """Normalize common PostgreSQL URLs to SQLAlchemy asyncpg format.

    Render usually provides a postgresql:// connection string. Some providers use
    postgres://. SQLAlchemy async engine needs postgresql+asyncpg://.
    """
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


DATABASE_URL = _to_asyncpg_url(settings.DATABASE_URL)

engine = create_async_engine(DATABASE_URL, echo=settings.SQL_ECHO)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
