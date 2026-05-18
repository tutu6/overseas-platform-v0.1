"""权限/角色守卫。

用法:
    @router.get("/foo", dependencies=[Depends(require_permission(Permissions.X))])
    或
    current = Depends(require_permission(Permissions.X))
"""
from __future__ import annotations

from typing import Iterable

from fastapi import Depends

from app.core.exceptions import PermissionDeniedError
from app.core.dependencies import CurrentUser, get_current_user


def require_permission(code: str):
    async def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if code not in current.permissions:
            raise PermissionDeniedError(f"Permission denied: {code}")
        return current
    return checker


def require_any_role(*role_codes: str):
    allowed = set(role_codes)

    async def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not (allowed & set(current.roles)):
            raise PermissionDeniedError(
                f"Permission denied: required role in {sorted(allowed)}"
            )
        return current
    return checker


def require_all_roles(*role_codes: str):
    required = set(role_codes)

    async def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not required.issubset(set(current.roles)):
            raise PermissionDeniedError(
                f"Permission denied: requires all roles {sorted(required)}"
            )
        return current
    return checker


def require_any_permission(*perm_codes: str):
    allowed: Iterable[str] = perm_codes

    async def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not any(code in current.permissions for code in allowed):
            raise PermissionDeniedError("Permission denied")
        return current
    return checker
