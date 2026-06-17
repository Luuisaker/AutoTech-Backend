from typing import AsyncGenerator

from anyio import get_current_task

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    async_scoped_session,
)
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import settings

engine = create_async_engine(settings.DATABASE_URL)

session_factory = async_scoped_session(
    async_sessionmaker(
        autoflush=False,
        autocommit=False,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    ),
    scopefunc=get_current_task,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = session_factory()

    try:
        yield session
    except:
        await session.rollback()
        raise
    finally:
        await session.close()


class Base(DeclarativeBase):
    pass
