"""角色 → 权限点 分配表。

# TODO(Q22): 角色-权限关系定义方式待团队拍板。当前实现:配置文件 + 启动同步(预倾向方案 C)。
# TODO(Q24): OPERATOR 不细分,后续按需要再拆。
# TODO(Q25): ADMIN 严格不触碰业务数据;若拍板调整,直接改本字典即可。
"""
from __future__ import annotations

from app.rbac.constants import Permissions

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "BUYER": [
        # 底座
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.BUYER_ORG_READ,
        # 业务(BUYER 工作台)
        Permissions.BUYER_DASHBOARD_READ,
        Permissions.PROJECT_READ,
        Permissions.PURCHASE_LIST_READ,
        Permissions.RFQ_READ,
        Permissions.ORDER_READ,
        Permissions.DOCUMENT_READ,
    ],
    "SUPPLIER": [
        # 底座
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.SUPPLIER_ORG_READ,
        Permissions.SUPPLIER_ORG_WRITE,
        # 业务(SUPPLIER 工作台)
        Permissions.SUPPLIER_DASHBOARD_READ,
        Permissions.MEMBERSHIP_READ,
        Permissions.PRODUCT_READ,
        Permissions.RFQ_RESPOND,
        Permissions.ORDER_READ,
    ],
    "OPERATOR": [
        # 底座
        Permissions.AUTH_LOGIN,
        Permissions.AUTH_LOGOUT,
        Permissions.AUTH_ME,
        Permissions.USER_READ,
        Permissions.BUYER_ORG_READ,
        Permissions.SUPPLIER_ORG_READ,
        # 业务(OPERATOR 后台)
        Permissions.OPERATOR_DASHBOARD_READ,
        Permissions.SUPPLIER_APPROVE,
        Permissions.PRODUCT_APPROVE,
        Permissions.ORDER_READ_ALL,
        Permissions.COUNTRY_WRITE,
        Permissions.RISK_READ,
    ],
    "ADMIN": [
        # 底座 + 系统(严格不触业务数据 - Q25)
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
        Permissions.SYSTEM_CONFIG,
    ],
}
