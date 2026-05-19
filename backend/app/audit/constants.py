"""审计资源类型与操作枚举。"""
from __future__ import annotations

from enum import Enum


class AuditResourceType(str, Enum):
    AUTH = "auth"
    USER = "user"
    ROLE = "role"
    PERMISSION = "permission"
    USER_ROLE = "user_role"
    BUYER_ORG = "buyer_org"
    SUPPLIER_ORG = "supplier_org"
    BUYER_MEMBER = "buyer_member"
    SUPPLIER_MEMBER = "supplier_member"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DISABLE = "DISABLE"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGIN_LOCKED = "LOGIN_LOCKED"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    # 自助资料变更(用户对自己账号的操作)
    PROFILE_UPDATE = "PROFILE_UPDATE"   # 改 name/phone 等低风险字段
    EMAIL_CHANGE = "EMAIL_CHANGE"       # 改登录邮箱
    USERNAME_CHANGE = "USERNAME_CHANGE" # 改/清空登录用户名
    PHONE_CHANGE = "PHONE_CHANGE"       # 改/清空登录手机号
    ROLE_ASSIGN = "ROLE_ASSIGN"
    ROLE_REVOKE = "ROLE_REVOKE"
