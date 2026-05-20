"""全局配置:从 .env 读取,Pydantic 校验后注入。"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 数据库 — PostgreSQL(本机 brew @16,端口 5433 以避开 EnterpriseDB pg13)
    DATABASE_URL: str = "postgresql+asyncpg://liujingjing@localhost:5433/overseas_supply_dev"

    # JWT
    JWT_SECRET_KEY: str = Field(..., min_length=16)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Super admin 种子(始终种入,生产唯一保留)
    SUPER_ADMIN_EMAIL: str = "superadmin@platform.local"
    SUPER_ADMIN_INITIAL_PASSWORD: str = "Aa123456789"

    # demo seed 开关:控制是否种入中建三局 BuyerOrg 与 admin/operator/buyer demo 账号
    # 本地开发推荐 true;**生产部署务必 false**
    SEED_DEMO_ACCOUNTS: bool = False

    # 日志
    LOG_LEVEL: str = "INFO"

    # CORS(逗号分隔,运行时拆为列表)
    CORS_ORIGINS_RAW: str = Field(
        default="http://localhost:3000", alias="CORS_ORIGINS"
    )

    # 登录限流(MVP 单机内存)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    LOGIN_RATE_LIMIT_MAX_FAILURES: int = 5
    LOGIN_RATE_LIMIT_LOCK_SECONDS: int = 300

    # 调试 API(/api/_debug/*)是否开启;生产应关闭
    ENABLE_DEBUG_API: bool = True

    # Refresh token cookie 配置(本机 http 开发用 SECURE=False;生产 https 必须 True)
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    REFRESH_COOKIE_MAX_AGE: int = 7 * 24 * 3600  # 7 天,与 refresh JWT TTL 一致
    REFRESH_COOKIE_SECURE: bool = False
    REFRESH_COOKIE_SAMESITE: str = "strict"  # strict / lax / none

    # CORS 允许携带凭证(refresh cookie 必需)
    CORS_ALLOW_CREDENTIALS: bool = True

    @computed_field  # type: ignore[misc]
    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [s.strip() for s in self.CORS_ORIGINS_RAW.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
