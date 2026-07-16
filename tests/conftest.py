"""Configuración global de pytest para AutoTech Backend.

Usa un esquema separado (test_schema) en la misma BD de desarrollo.
Esto evita tener que crear otra BD y aísla completamente los datos.
"""

from typing import AsyncGenerator
from uuid import uuid4
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from src.config.settings import settings
from src.config.database import Base
from src.config.server import App
from src.config.models import (
    User as UserModel,
    UserRole as UserRoleModel,
    CreditLevel as CreditLevelModel,
)
from src.modules.users.infrastructure.auth import create_access_token

# ── Test engine: same DB, separate schema ─────────────────────
TEST_SCHEMA = "test_schema"

test_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={
        "server_settings": {"search_path": TEST_SCHEMA},
    },
)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


async def _ensure_schema():
    """Create test schema if it doesn't exist."""
    async with test_engine.connect() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}'))
        await conn.commit()

# ── Test app ──────────────────────────────────────────────────
app_instance = App()
fastapi_app = app_instance.server


# ── Fixtures ───────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def test_app():
    yield fastapi_app


@pytest_asyncio.fixture
async def client(test_app) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables in test_schema before each test, drop after."""
    try:
        await _ensure_schema()
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception:
        pass  # Sin BD disponible — tests unitarios corren igual

    # Seed credit levels
    try:
        async with test_session_factory() as session:
            existing = await session.get(CreditLevelModel, 1)
            if not existing:
                levels = [
                    CreditLevelModel(level=1, points_required=0, credit_multiplier=1.0, min_down_payment_pct=60, base_parts_limit=150),
                    CreditLevelModel(level=2, points_required=300, credit_multiplier=2.0, min_down_payment_pct=50, base_parts_limit=300),
                    CreditLevelModel(level=3, points_required=900, credit_multiplier=4.0, min_down_payment_pct=40, base_parts_limit=600),
                    CreditLevelModel(level=4, points_required=2700, credit_multiplier=8.0, min_down_payment_pct=30, base_parts_limit=1200),
                ]
                for lvl in levels:
                    session.add(lvl)
                await session.commit()
    except Exception:
        pass

    yield

    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception:
        pass


@pytest_asyncio.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session
        await session.rollback()


# ── Helper factories ──────────────────────────────────────────


async def create_test_user(
    db_session,
    email: str | None = None,
    role: str = "CLIENT",
) -> UserModel:
    """Create a test user directly in the database.
    
    Para tests sin BD, usar UserDTO manualmente.
    """
    email = email or f"test-{uuid4().hex[:8]}@example.com"
    import bcrypt
    pw_hash = bcrypt.hashpw(b"testpass123", bcrypt.gensalt()).decode("utf-8")
    user = UserModel(
        email=email,
        password_hash=pw_hash,
        first_name="Test",
        last_name="User",
        ci=f"V-{uuid4().hex[:8].upper()}",
        phone="+584141234567",
        credit_level=1,
        parts_credit_limit=150.0,
        service_credit_limit=50.0,
        credit_points=0.0,
        total_parts_debt=0.0,
        total_service_debt=0.0,
    )
    db_session.add(user)
    await db_session.flush()
    role_model = UserRoleModel(user_id=user.id, role=role)
    db_session.add(role_model)
    await db_session.flush()
    await db_session.refresh(user)
    return user


def get_test_token(user_id: str, roles: list[str] | None = None) -> str:
    """Generate a JWT for testing."""
    return create_access_token(
        data={"sub": user_id, "roles": roles or ["CLIENT"]}
    )


async def auth_header(client, user_id: str, roles: list[str] | None = None):
    """Return headers dict with Bearer token."""
    token = get_test_token(user_id, roles)
    return {"Authorization": f"Bearer {token}"}
