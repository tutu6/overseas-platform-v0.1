"""权限点常量。

命名约定:`resource:action`,小写冒号分隔。
新增权限只在此类追加,不要散落到业务代码。
"""
from __future__ import annotations


class Permissions:
    # ----- 底座 -----
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
    SUPPLIER_ORG_WRITE = "supplier_org:write"

    # system
    AUDIT_LOG_READ = "audit:read"
    SYSTEM_CONFIG = "system:config"

    # ----- 业务权限点(本轮为导航/侧边栏占位,后续业务模块上线时复用)-----
    # BUYER 工作台
    BUYER_DASHBOARD_READ = "buyer:dashboard:read"
    PROJECT_READ = "project:read"
    PURCHASE_LIST_READ = "purchase_list:read"
    RFQ_READ = "rfq:read"
    ORDER_READ = "order:read"
    DOCUMENT_READ = "document:read"

    # SUPPLIER 工作台
    SUPPLIER_DASHBOARD_READ = "supplier:dashboard:read"
    MEMBERSHIP_READ = "membership:read"
    PRODUCT_READ = "product:read"
    RFQ_RESPOND = "rfq:respond"

    # OPERATOR 后台
    OPERATOR_DASHBOARD_READ = "operator:dashboard:read"
    SUPPLIER_APPROVE = "supplier:approve"
    PRODUCT_APPROVE = "product:approve"
    ORDER_READ_ALL = "order:read:all"
    COUNTRY_WRITE = "country:write"
    RISK_READ = "risk:read"


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
    Permissions.SUPPLIER_ORG_WRITE: {"name": "编辑/入驻供应商组织", "module": "supplier_org"},
    Permissions.AUDIT_LOG_READ: {"name": "查看审计日志", "module": "audit"},
    Permissions.SYSTEM_CONFIG: {"name": "系统配置", "module": "system"},

    # BUYER 工作台
    Permissions.BUYER_DASHBOARD_READ: {"name": "采购方工作台", "module": "buyer"},
    Permissions.PROJECT_READ: {"name": "查看项目", "module": "project"},
    Permissions.PURCHASE_LIST_READ: {"name": "查看采购清单", "module": "purchase_list"},
    Permissions.RFQ_READ: {"name": "查看询价单", "module": "rfq"},
    Permissions.ORDER_READ: {"name": "查看订单", "module": "order"},
    Permissions.DOCUMENT_READ: {"name": "查看单据", "module": "document"},

    # SUPPLIER 工作台
    Permissions.SUPPLIER_DASHBOARD_READ: {"name": "供应商工作台", "module": "supplier"},
    Permissions.MEMBERSHIP_READ: {"name": "会员中心", "module": "membership"},
    Permissions.PRODUCT_READ: {"name": "查看商品", "module": "product"},
    Permissions.RFQ_RESPOND: {"name": "响应询价", "module": "rfq"},

    # OPERATOR 后台
    Permissions.OPERATOR_DASHBOARD_READ: {"name": "运营工作台", "module": "operator"},
    Permissions.SUPPLIER_APPROVE: {"name": "审核供应商", "module": "supplier"},
    Permissions.PRODUCT_APPROVE: {"name": "审核商品", "module": "product"},
    Permissions.ORDER_READ_ALL: {"name": "查看全平台订单", "module": "order"},
    Permissions.COUNTRY_WRITE: {"name": "维护国别准入", "module": "country"},
    Permissions.RISK_READ: {"name": "风控驾驶舱", "module": "risk"},
}


# 角色元数据(用于启动种子角色)
ROLE_META: dict[str, dict[str, str]] = {
    "BUYER": {"name": "项目部采购员", "description": "采购方项目部成员"},
    "SUPPLIER": {"name": "供应商", "description": "海外材料供货方"},
    "OPERATOR": {"name": "平台运营", "description": "平台业务管理员,可见业务数据"},
    "ADMIN": {"name": "系统管理员", "description": "系统管理员,负责账号/权限/系统配置,不触碰业务数据"},
}
