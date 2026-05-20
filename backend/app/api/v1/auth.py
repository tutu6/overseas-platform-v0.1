"""认证路由 /api/v1/auth/*"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser, get_current_user
from app.core.exceptions import NotAuthenticatedError, success
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.db.models.user import User, UserStatus
from jose import JWTError
from urllib.parse import urlparse
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
from app.schemas.me import ChangeEmailIn, ChangePhoneIn, ChangeUsernameIn, ProfileUpdateIn
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
        company_name=body.company_name,
        unified_social_credit_code=body.unified_social_credit_code,
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
        name=body.name,
        phone=body.phone,
        password=body.password,
        company_name=body.company_name,
        country_code=body.country_code,
        registration_no=body.registration_no,
        language_preference=body.language_preference,
        request=request,
    )
    return success(RegisterOut(user_id=user.id, email=user.email).model_dump())


def _origin_allowed(origin_header: str | None, allowed: list[str]) -> bool:
    """Origin/Referer 白名单校验(CSRF 防御)。

    取 origin_header 的 scheme://host[:port],与 allowed 列表精确匹配。
    """
    if not origin_header:
        return False
    parsed = urlparse(origin_header)
    if not parsed.scheme or not parsed.hostname:
        return False
    port = f":{parsed.port}" if parsed.port else ""
    normalized = f"{parsed.scheme}://{parsed.hostname}{port}"
    return normalized in allowed


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """统一封装:把 refresh token 写入 httpOnly cookie。"""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


@router.post("/login", summary="登录(access 在 body,refresh 在 httpOnly cookie)")
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login(
        db, identifier=body.identifier, password=body.password, request=request
    )
    # refresh 不入 body,通过 httpOnly cookie 下发
    _set_refresh_cookie(response, tokens["refresh_token"])
    return success(TokenOut(
        access_token=tokens["access_token"],
        token_type=tokens["token_type"],
        expires_in=tokens["expires_in"],
    ).model_dump())


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


@router.post("/refresh", summary="用 httpOnly cookie 中的 refresh token 换新 access(并轮转 refresh)")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # 1. CSRF 防御:Origin/Referer 必须在白名单
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not _origin_allowed(origin, settings.CORS_ORIGINS):
        raise NotAuthenticatedError("Invalid origin")

    # 2. 从 httpOnly cookie 读 refresh token
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise NotAuthenticatedError("No refresh token")

    # 3. 解码 + 校验(type 必须 refresh)
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except JWTError:
        raise NotAuthenticatedError("Invalid refresh token")

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise NotAuthenticatedError("Invalid token payload")
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        raise NotAuthenticatedError("Invalid token payload")

    # 4. 用户必须 ACTIVE
    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise NotAuthenticatedError("User unavailable")

    # 5. 签新 access + 新 refresh(refresh 轮转,降低盗用窗口)
    new_access, expires_in = create_access_token(user.id, user.email)
    new_refresh = create_refresh_token(user.id, user.email)

    # 6. 新 refresh 写回 cookie
    _set_refresh_cookie(response, new_refresh)

    # 7. 返回新 access(refresh 静默,**不写 audit_logs** 避免噪音)
    return success({
        "access_token": new_access,
        "token_type": "Bearer",
        "expires_in": expires_in,
    })


@router.post("/logout", summary="登出(清 cookie + 写审计)")
async def logout(
    request: Request,
    response: Response,
    current: CurrentUser = Depends(require_permission(Permissions.AUTH_LOGOUT)),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.logout(
        db, user_id=current.id, user_email=current.email, request=request
    )
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
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


@router.post("/me/phone", summary="修改/清空自己登录手机号(需当前密码)")
async def change_my_phone(
    body: ChangePhoneIn,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await me_service.change_phone(
        db,
        user_id=current.id,
        new_phone=body.new_phone,
        current_password=body.current_password,
        request=request,
    )
    return success(_me_payload(user))
