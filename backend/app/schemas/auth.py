"""认证相关 schemas。"""
from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password_strength


# 用户名规则:3-50 位,字母/数字/下划线/短横,不能纯数字
USERNAME_REGEX = re.compile(r"^(?![0-9]+$)[A-Za-z0-9_\-]{3,50}$")

# 统一社会信用代码:严格 18 位,大写字母 + 数字(国标 GB 32100-2015)
USC_REGEX = re.compile(r"^[0-9A-Z]{18}$")


def _validate_password(v: str) -> str:
    if not validate_password_strength(v):
        raise ValueError("密码长度 8-32 位,至少包含 1 个字母和 1 个数字")
    return v


def _validate_username_optional(v: str | None) -> str | None:
    if v is None or v == "":
        return None
    if not USERNAME_REGEX.match(v):
        raise ValueError("用户名 3-50 位,只能含字母/数字/下划线/短横,且不能纯数字")
    return v


class BuyerRegisterIn(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    password: str
    # 公司信息:按统一社会信用代码识别企业(不存在则建新组织,存在则加入)
    company_name: str = Field(..., min_length=1, max_length=200)
    unified_social_credit_code: str = Field(..., min_length=18, max_length=18)

    @field_validator("password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str | None) -> str | None:
        return _validate_username_optional(v)

    @field_validator("unified_social_credit_code")
    @classmethod
    def _check_usc(cls, v: str) -> str:
        if not USC_REGEX.match(v):
            raise ValueError("统一社会信用代码必须为 18 位大写字母与数字")
        return v


class SupplierRegisterIn(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    password: str
    company_name: str = Field(..., min_length=1, max_length=200)
    business_license_no: str = Field(..., min_length=1, max_length=100)

    @field_validator("password")
    @classmethod
    def _check_pwd(cls, v: str) -> str:
        return _validate_password(v)

    @field_validator("username")
    @classmethod
    def _check_username(cls, v: str | None) -> str | None:
        return _validate_username_optional(v)


class RegisterOut(BaseModel):
    user_id: int
    email: str


class LoginIn(BaseModel):
    # identifier:用户名 或 邮箱(含 `@` 走 email 查找,否则走 username 查找)
    identifier: str = Field(..., min_length=3, max_length=255)
    password: str


class TokenOut(BaseModel):
    """登录响应。refresh_token **不在 body**,通过 httpOnly cookie 下发。"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_new(cls, v: str) -> str:
        if not validate_password_strength(v):
            raise ValueError("新密码长度 8-32 位,至少包含 1 个字母和 1 个数字")
        return v


class OrganizationOut(BaseModel):
    type: str
    id: int
    name: str
    is_owner: bool


class MeOut(BaseModel):
    id: int
    email: str
    username: str | None = None
    name: str
    phone: str | None = None
    status: str
    must_change_password: bool
    roles: list[str]
    permissions: list[str]
    organization: OrganizationOut | None = None
