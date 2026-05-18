"""认证路由 /api/v1/auth/*"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.schemas.auth import (
    BuyerRegisterIn,
    ChangePasswordIn,
    LoginIn,
    MeOut,
    RegisterOut,
    SupplierRegisterIn,
    TokenOut,
)
from app.schemas.me import ChangeEmailIn, ChangeUsernameIn, ProfileUpdateIn
from app.services import auth_service, me_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register/buyer", summary="BUYER 自助注册")
async def register_buyer(
    body: BuyerRegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register_buyer(
        db,
        email=body.email,
        username=body.username,
        name=body.name,
        phone=body.phone,
        password=body.password,
        request=request,
    )
    return success(RegisterOut(user_id=user.id, email=user.email).model_dump())


@router.post("/register/supplier", summary="SUPPLIER 自助注册")
async def register_supplier(
    body: SupplierRegisterIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.register_supplier(
        db,
        email=body.email,
        username=body.username,
        name=body.name,
        phone=body.phone,
        password=body.password,
        company_name=body.company_name,
        business_license_no=body.business_license_no,
        request=request,
    )
    return success(RegisterOut(user_id=user.id, email=user.email).model_dump())


@router.post("/login", summary="登录(返回 JWT,不返回 permissions)")
async def login(
    body: LoginIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login(
        db, identifier=body.identifier, password=body.password, request=request
    )
    return success(TokenOut(**tokens).model_dump())


@router.get("/me", summary="当前用户:roles + permissions + organization")
async def me(current: CurrentUser = Depends(get_current_user)):
    org = asdict(current.organization) if current.organization else None
    data = MeOut(
        id=current.id,
        email=current.email,
        username=current.username,
        name=current.name,
        phone=current.phone,
        status=current.status,
        must_change_password=current.must_change_password,
        roles=current.roles,
        permissions=current.permissions,
        organization=org,
    ).model_dump()
    return success(data)


@router.post("/logout", summary="登出(无状态,只写审计)")
async def logout(
    request: Request,
    current: CurrentUser = Depends(require_permission(Permissions.AUTH_LOGOUT)),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout(
        db, user_id=current.id, user_email=current.email, request=request
    )
    return success(None)


@router.post("/change-password", summary="修改自己密码")
async def change_password(
    body: ChangePasswordIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.change_password(
        db,
        user_id=current.id,
        old_password=body.old_password,
        new_password=body.new_password,
        request=request,
    )
    return success(None)


# ----- 自助资料管理 -----

def _me_payload(user) -> dict:
    """读取 User → 拼一份精简的资料返回(不含 roles/permissions)。"""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "name": user.name,
        "phone": user.phone,
        "status": user.status,
        "must_change_password": user.must_change_password,
    }


@router.patch("/me/profile", summary="修改自己基础资料(name / phone,无需密码)")
async def update_my_profile(
    body: ProfileUpdateIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.update_profile(
        db,
        user_id=current.id,
        name=body.name,
        phone=body.phone,
        request=request,
    )
    return success(_me_payload(user))


@router.post("/me/email", summary="修改自己登录邮箱(需当前密码)")
async def change_my_email(
    body: ChangeEmailIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.change_email(
        db,
        user_id=current.id,
        new_email=body.new_email,
        current_password=body.current_password,
        request=request,
    )
    return success(_me_payload(user))


@router.post("/me/username", summary="修改/清空自己登录用户名(需当前密码)")
async def change_my_username(
    body: ChangeUsernameIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.change_username(
        db,
        user_id=current.id,
        new_username=body.new_username,
        current_password=body.current_password,
        request=request,
    )
    return success(_me_payload(user))
