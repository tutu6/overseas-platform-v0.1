// 权限点常量(与后端 app/rbac/constants.py 同步)。

export const Permissions = {
  // ----- 底座 -----
  AUTH_LOGIN: "auth:login",
  AUTH_LOGOUT: "auth:logout",
  AUTH_ME: "auth:me",

  USER_READ: "user:read",
  USER_CREATE: "user:create",
  USER_UPDATE: "user:update",
  USER_DISABLE: "user:disable",

  ROLE_READ: "role:read",
  ROLE_MANAGE: "role:manage",
  PERMISSION_READ: "permission:read",

  USER_ROLE_ASSIGN: "user_role:assign",
  USER_ROLE_REVOKE: "user_role:revoke",

  BUYER_ORG_READ: "buyer_org:read",
  SUPPLIER_ORG_READ: "supplier_org:read",
  SUPPLIER_ORG_WRITE: "supplier_org:write",

  AUDIT_LOG_READ: "audit:read",
  SYSTEM_CONFIG: "system:config",

  // ----- 业务(本轮为导航占位)-----
  BUYER_DASHBOARD_READ: "buyer:dashboard:read",
  PROJECT_READ: "project:read",
  PURCHASE_LIST_READ: "purchase_list:read",
  RFQ_READ: "rfq:read",
  ORDER_READ: "order:read",
  DOCUMENT_READ: "document:read",

  SUPPLIER_DASHBOARD_READ: "supplier:dashboard:read",
  MEMBERSHIP_READ: "membership:read",
  PRODUCT_READ: "product:read",
  RFQ_RESPOND: "rfq:respond",

  OPERATOR_DASHBOARD_READ: "operator:dashboard:read",
  SUPPLIER_APPROVE: "supplier:approve",
  PRODUCT_APPROVE: "product:approve",
  ORDER_READ_ALL: "order:read:all",
  COUNTRY_WRITE: "country:write",
  RISK_READ: "risk:read",
} as const;

export type PermissionCode = (typeof Permissions)[keyof typeof Permissions];
