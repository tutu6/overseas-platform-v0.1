"""内部账号管理路由 /api/v1/admin/users"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.user import AdminUserCreateIn, AdminUserListOut, AdminUserOut
from app.services import user_service

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.post("", summary="创建 ADMIN / OPERATOR 内部账号")
async def create_user(
    body: AdminUserCreateIn,
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    user = await user_service.create_internal_user(
        db,
        email=body.email,
        username=body.username,
        name=body.name,
        password=body.password,
        role=body.role,
        must_change_password=body.must_change_password,
        actor_user_id=current.id,
        actor_user_email=current.email,
        request=request,
    )
    out = AdminUserOut(
        id=user.id,
        email=user.email,
        username=user.username,
        name=user.name,
        status=user.status,
        must_change_password=user.must_change_password,
        roles=[body.role],
    )
    return success(out.model_dump())


@router.get("", summary="用户列表(内部)")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current: CurrentUser = Depends(require_permission(Permissions.USER_MANAGE)),
    db: AsyncSession = Depends(get_db),
):
    items, total = await user_service.list_users(db, page=page, page_size=page_size)
    out = AdminUserListOut(
        items=[
            AdminUserOut(
                id=u.id,
                email=u.email,
                username=u.username,
                name=u.name,
                status=u.status,
                must_change_password=u.must_change_password,
                roles=roles,
            )
            for u, roles in items
        ],
        total=total,
    )
    return success(out.model_dump())
