from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from .config import settings

engine = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """
    Initialize the async engine + sessionmaker and create tables if missing.

    This setup expects PostgreSQL with asyncpg.
    """
    global engine, SessionLocal

    db_url = settings.EFFECTIVE_DATABASE_URL
    if not db_url:
        raise RuntimeError("DATABASE_URL is not configured. Set DATABASE_URL to a PostgreSQL asyncpg URL.")

    if engine is None:
        engine = create_async_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,  # Helps avoid stale connections
        )

    if SessionLocal is None:
        SessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    # Import models so SQLModel registers table metadata before create_all
    from . import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session():
    """
    FastAPI dependency that yields an AsyncSession.
    """
    if SessionLocal is None:
        raise RuntimeError("DB is not initialized. Check DATABASE_URL and init_db().")
    async with SessionLocal() as session:
        yield session
