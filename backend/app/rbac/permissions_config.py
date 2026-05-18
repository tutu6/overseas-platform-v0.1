"""角色 → 权限点 分配表。

# TODO(Q22): 角色-权限关系定义方式待团队拍板。当前实现:配置文件 + 启动同步(预倾向方案 C)。
# TODO(Q24): OPERATOR 不细分,后续按需要再拆。
# TODO(Q25): ADMIN 严格不触碰业务数据;若拍板调整,直接改本字典即可。
"""
from __future__ import annotations

from app.rbac.constants import Permissions

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "BUYER": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.BUYER_ORG_READ,
    ],
    "SUPPLIER": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.SUPPLIER_ORG_READ,
    ],
    "OPERATOR": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.USER_READ,
        Permissions.BUYER_ORG_READ,
        Permissions.SUPPLIER_ORG_READ,
    ],
    "ADMIN": [
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.USER_READ,
        Permissions.USER_CREATE,
        Permissions.USER_UPDATE,
        Permissions.USER_DISABLE,
        Permissions.ROLE_READ,
        Permissions.ROLE_MANAGE,
        Permissions.PERMISSION_READ,
        Permissions.USER_ROLE_ASSIGN,
        Permissions.USER_ROLE_REVOKE,
        Permissions.AUDIT_LOG_READ,
    ],
}
