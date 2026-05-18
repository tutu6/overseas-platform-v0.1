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

    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./dev.db"

    # JWT
    JWT_SECRET_KEY: str = Field(..., min_length=16)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Super admin 种子
    SUPER_ADMIN_EMAIL: str = "superadmin@platform.local"
    SUPER_ADMIN_INITIAL_PASSWORD: str = "ChangeMe123"

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

    @computed_field  # type: ignore[misc]
    @property
    def CORS_ORIGINS(self) -> List[str]:
        return [s.strip() for s in self.CORS_ORIGINS_RAW.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
