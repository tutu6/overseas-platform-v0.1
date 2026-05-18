"""pytest fixtures。

每个测试用独立 SQLite(内存),启动同步 RBAC + seed,httpx AsyncClient 直连 ASGI。
"""
from __future__ import annotations

import os

# 测试前设置必要环境变量(避免 .env 缺失时启动失败)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-please-change-1234567890")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SUPER_ADMIN_EMAIL", "superadmin@platform.local")
os.environ.setdefault("SUPER_ADMIN_INITIAL_PASSWORD", "ChangeMe123")

import asyncio  # noqa: E402
from typing import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db import models as _models  # noqa: E402,F401
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.rbac.sync import sync_rbac  # noqa: E402
from app.seed import run_all_seeds  # noqa: E402
from app.services.rate_limit import login_rate_limiter  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_engine():
    # 每个测试一个内存库,互不污染
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)

    # 同步 RBAC + 种子,使用测试库
    async with SessionLocal() as db:
        await sync_rbac(db)
        await run_all_seeds(db)

    async def override_get_db():
        async with SessionLocal() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    login_rate_limiter.clear_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    login_rate_limiter.clear_all()
