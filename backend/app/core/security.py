"""密码哈希 + JWT 编解码。"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 密码规则:8-32 位,至少 1 字母 + 1 数字
PASSWORD_REGEX = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*#?&^_-]{8,32}$")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(plain, hashed)
    except Exception:
        return False


def validate_password_strength(plain: str) -> bool:
    return bool(PASSWORD_REGEX.match(plain))


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, email: str) -> tuple[str, int]:
    expires_in = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    exp = _now_utc() + timedelta(seconds=expires_in)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "iat": int(_now_utc().timestamp()),
        "exp": int(exp.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_in


def create_refresh_token(user_id: int, email: str) -> str:
    exp = _now_utc() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "refresh",
        "iat": int(_now_utc().timestamp()),
        "exp": int(exp.timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str, expected_type: Literal["access", "refresh"] = "access") -> dict[str, Any]:
    """解码并校验 JWT。失败抛 JWTError(由调用方转 401)。"""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != expected_type:
        raise JWTError("Wrong token type")
    return payload
