"""权限点常量。

命名约定:`resource:action`,小写冒号分隔。
新增权限只在此类追加,不要散落到业务代码。
"""
from __future__ import annotations


class Permissions:
    # auth
    AUTH_LOGIN = "auth:login"
    AUTH_LOGOUT = "auth:logout"
    AUTH_ME = "auth:me"

    # user
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DISABLE = "user:disable"

    # role / permission
    ROLE_READ = "role:read"
    ROLE_MANAGE = "role:manage"
    PERMISSION_READ = "permission:read"

    # rbac
    USER_ROLE_ASSIGN = "user_role:assign"
    USER_ROLE_REVOKE = "user_role:revoke"

    # org
    BUYER_ORG_READ = "buyer_org:read"
    SUPPLIER_ORG_READ = "supplier_org:read"

    # system
    AUDIT_LOG_READ = "audit:read"


# 权限点元数据(用于启动同步:name / module / description)
PERMISSION_META: dict[str, dict[str, str]] = {
    Permissions.AUTH_LOGIN: {"name": "登录", "module": "auth"},
    Permissions.AUTH_LOGOUT: {"name": "登出", "module": "auth"},
    Permissions.AUTH_ME: {"name": "获取当前用户", "module": "auth"},
    Permissions.USER_READ: {"name": "查看用户", "module": "user"},
    Permissions.USER_CREATE: {"name": "创建用户", "module": "user"},
    Permissions.USER_UPDATE: {"name": "修改用户", "module": "user"},
    Permissions.USER_DISABLE: {"name": "禁用用户", "module": "user"},
    Permissions.ROLE_READ: {"name": "查看角色", "module": "role"},
    Permissions.ROLE_MANAGE: {"name": "管理角色", "module": "role"},
    Permissions.PERMISSION_READ: {"name": "查看权限点", "module": "permission"},
    Permissions.USER_ROLE_ASSIGN: {"name": "分配角色", "module": "user_role"},
    Permissions.USER_ROLE_REVOKE: {"name": "撤销角色", "module": "user_role"},
    Permissions.BUYER_ORG_READ: {"name": "查看采购方组织", "module": "buyer_org"},
    Permissions.SUPPLIER_ORG_READ: {"name": "查看供应商组织", "module": "supplier_org"},
    Permissions.AUDIT_LOG_READ: {"name": "查看审计日志", "module": "audit"},
}


# 角色元数据(用于启动种子角色)
ROLE_META: dict[str, dict[str, str]] = {
    "BUYER": {"name": "项目部采购员", "description": "采购方项目部成员"},
    "SUPPLIER": {"name": "供应商", "description": "海外材料供货方"},
    "OPERATOR": {"name": "平台运营", "description": "平台业务管理员,可见业务数据"},
    "ADMIN": {"name": "系统管理员", "description": "系统管理员,负责账号/权限/系统配置,不触碰业务数据"},
}
