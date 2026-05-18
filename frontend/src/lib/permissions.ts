// 权限点常量(与后端 app/rbac/constants.py 同步)。

export const Permissions = {
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
  AUDIT_LOG_READ: "audit:read",
} as const;

export type PermissionCode = (typeof Permissions)[keyof typeof Permissions];
