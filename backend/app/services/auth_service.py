"""认证 service:注册、登录、改密。"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.exceptions import (
    AccountDisabledError,
    ConflictError,
    InvalidCredentialsError,
    NotFoundError,
    TooManyAttemptsError,
    ValidationFailedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.db.models.audit_log import AuditStatus
from app.db.models.buyer_member import BuyerMember
from app.db.models.buyer_organization import BuyerOrganization
from app.db.models.role import Role, RoleCode
from app.db.models.supplier_member import SupplierMember
from app.db.models.supplier_organization import SupplierOrganization
from app.db.models.user import User, UserStatus
from app.db.models.user_role import UserRole
from app.services.rate_limit import login_rate_limiter

logger = logging.getLogger(__name__)

# 中建三局组织 code,种子保证存在
CSCEC3B_CODE = "CSCEC3B"


def _client_ip(request: Request | None) -> str:
    if request is None or request.client is None:
        return "-"
    return request.client.host or "-"


async def _get_role(db: AsyncSession, code: str) -> Role:
    row = await db.execute(select(Role).where(Role.code == code))
    role = row.scalar_one_or_none()
    if role is None:
        raise NotFoundError(f"Role not found: {code}")
    return role


async def _email_exists(db: AsyncSession, email: str) -> bool:
    row = await db.execute(select(User.id).where(User.email == email))
    return row.scalar_one_or_none() is not None


async def _username_exists(db: AsyncSession, username: str) -> bool:
    row = await db.execute(select(User.id).where(User.username == username))
    return row.scalar_one_or_none() is not None


async def _find_user_by_identifier(db: AsyncSession, identifier: str) -> User | None:
    """identifier 含 '@' → 当 email 查;否则当 username 查。"""
    ident = identifier.strip()
    if "@" in ident:
        row = await db.execute(select(User).where(User.email == ident))
    else:
        row = await db.execute(select(User).where(User.username == ident))
    return row.scalar_one_or_none()


async def register_buyer(
    db: AsyncSession,
    *,
    email: str,
    name: str,
    phone: str | None,
    password: str,
    username: str | None = None,
    request: Request | None = None,
) -> User:
    if not validate_password_strength(password):
        raise ValidationFailedError("密码不符合规则(8-32 位,至少 1 字母 1 数字)")
    if await _email_exists(db, email):
        raise ConflictError("Email 已存在")
    if username and await _username_exists(db, username):
        raise ConflictError("用户名已存在")

    # 取中建三局组织
    org_row = await db.execute(
        select(BuyerOrganization).where(BuyerOrganization.code == CSCEC3B_CODE)
    )
    org = org_row.scalar_one_or_none()
    if org is None:
        # 种子异常,作为运维问题处理
        raise NotFoundError("默认采购方组织未初始化,请联系运维")

    user = User(
        email=email,
        username=username,
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()

    db.add(BuyerMember(user_id=user.id, buyer_org_id=org.id, is_owner=False))
    role = await _get_role(db, RoleCode.BUYER)
    db.add(UserRole(user_id=user.id, role_id=role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        request=request,
        extra={"role": RoleCode.BUYER, "buyer_org_id": org.id},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def register_supplier(
    db: AsyncSession,
    *,
    email: str,
    name: str,
    phone: str | None,
    password: str,
    company_name: str,
    business_license_no: str,
    username: str | None = None,
    request: Request | None = None,
) -> User:
    if not validate_password_strength(password):
        raise ValidationFailedError("密码不符合规则(8-32 位,至少 1 字母 1 数字)")
    if await _email_exists(db, email):
        raise ConflictError("Email 已存在")
    if username and await _username_exists(db, username):
        raise ConflictError("用户名已存在")
    # 营业执照唯一校验
    row = await db.execute(
        select(SupplierOrganization.id).where(
            SupplierOrganization.business_license_no == business_license_no
        )
    )
    if row.scalar_one_or_none() is not None:
        raise ConflictError("营业执照号已存在")

    user = User(
        email=email,
        username=username,
        name=name,
        phone=phone,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        must_change_password=False,
    )
    db.add(user)
    await db.flush()

    org = SupplierOrganization(
        name=company_name,
        business_license_no=business_license_no,
        status="DRAFT",
    )
    db.add(org)
    await db.flush()

    db.add(SupplierMember(user_id=user.id, supplier_org_id=org.id, is_owner=True))
    role = await _get_role(db, RoleCode.SUPPLIER)
    db.add(UserRole(user_id=user.id, role_id=role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        request=request,
        extra={"role": RoleCode.SUPPLIER, "supplier_org_id": org.id},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def login(
    db: AsyncSession,
    *,
    identifier: str,
    password: str,
    request: Request | None = None,
) -> dict:
    """identifier 支持邮箱(含 '@')或用户名。限流以 identifier+ip 为 key。"""
    ip = _client_ip(request)
    rate_key = identifier.strip().lower()

    if login_rate_limiter.is_locked(rate_key, ip):
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.LOGIN_LOCKED,
            status=AuditStatus.FAILED,
            user_email=identifier,
            request=request,
            error_message="locked",
            extra={"identifier": identifier},
        )
        raise TooManyAttemptsError()

    user = await _find_user_by_identifier(db, identifier)

    # 用户不存在 / 密码错误 → 统一返回 401,防枚举
    if user is None or not verify_password(password, user.password_hash):
        locked_now = login_rate_limiter.record_failure(rate_key, ip)
        action = AuditAction.LOGIN_LOCKED if locked_now else AuditAction.LOGIN_FAILED
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=action,
            status=AuditStatus.FAILED,
            user_email=user.email if user else identifier,
            user_id=user.id if user else None,
            request=request,
            error_message="invalid credentials",
            extra={"identifier": identifier},
        )
        if locked_now:
            raise TooManyAttemptsError()
        raise InvalidCredentialsError()

    if user.status == UserStatus.DISABLED:
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.LOGIN_FAILED,
            status=AuditStatus.FAILED,
            user_id=user.id,
            user_email=user.email,
            request=request,
            error_message="account disabled",
        )
        raise AccountDisabledError()

    # 成功
    login_rate_limiter.reset(rate_key, ip)
    access_token, expires_in = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id, user.email)
    await write_audit(
        db,
        resource_type=AuditResourceType.AUTH,
        action=AuditAction.LOGIN_SUCCESS,
        user_id=user.id,
        user_email=user.email,
        request=request,
        extra={"identifier_used": "email" if "@" in identifier else "username"},
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": expires_in,
    }


async def change_password(
    db: AsyncSession,
    *,
    user_id: int,
    old_password: str,
    new_password: str,
    request: Request | None = None,
) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if not verify_password(old_password, user.password_hash):
        await write_audit(
            db,
            resource_type=AuditResourceType.AUTH,
            action=AuditAction.PASSWORD_CHANGE,
            status=AuditStatus.FAILED,
            user_id=user.id,
            user_email=user.email,
            request=request,
            error_message="old password incorrect",
        )
        raise InvalidCredentialsError("旧密码错误")
    if not validate_password_strength(new_password):
        raise ValidationFailedError("新密码不符合规则")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False

    await write_audit(
        db,
        resource_type=AuditResourceType.AUTH,
        action=AuditAction.PASSWORD_CHANGE,
        user_id=user.id,
        user_email=user.email,
        request=request,
        commit=False,
    )
    await db.commit()


async def logout(
    db: AsyncSession,
    *,
    user_id: int,
    user_email: str,
    request: Request | None = None,
) -> None:
    """无状态 JWT 登出:仅写审计,前端自行清 token。"""
    await write_audit(
        db,
        resource_type=AuditResourceType.AUTH,
        action=AuditAction.LOGOUT,
        user_id=user_id,
        user_email=user_email,
        request=request,
    )
