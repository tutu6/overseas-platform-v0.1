"""内部账号管理 service。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.security import hash_password, validate_password_strength
from app.db.models.permission import Permission  # noqa: F401  (确保 metadata 注册)
from app.db.models.role import Role, RoleCode
from app.db.models.user import User, UserStatus
from app.db.models.user_role import UserRole

ALLOWED_INTERNAL_ROLES = {RoleCode.ADMIN, RoleCode.OPERATOR}


async def create_internal_user(
    db: AsyncSession,
    *,
    email: str,
    name: str,
    password: str,
    role: str,
    must_change_password: bool,
    actor_user_id: int,
    actor_user_email: str,
    username: str | None = None,
    request: Request | None = None,
) -> User:
    if role not in ALLOWED_INTERNAL_ROLES:
        # 业务用户必须走自助注册
        raise ValidationFailedError(
            f"该接口仅允许创建 {sorted(ALLOWED_INTERNAL_ROLES)},BUYER/SUPPLIER 请走自助注册"
        )
    if not validate_password_strength(password):
        raise ValidationFailedError("密码不符合规则(8-32 位,至少 1 字母 1 数字)")
    row = await db.execute(select(User.id).where(User.email == email))
    if row.scalar_one_or_none() is not None:
        raise ConflictError("Email 已存在")
    if username:
        row2 = await db.execute(select(User.id).where(User.username == username))
        if row2.scalar_one_or_none() is not None:
            raise ConflictError("用户名已存在")

    role_row = await db.execute(select(Role).where(Role.code == role))
    role_obj = role_row.scalar_one_or_none()
    if role_obj is None:
        raise NotFoundError(f"Role not found: {role}")

    user = User(
        email=email,
        username=username,
        name=name,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        must_change_password=must_change_password,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role_obj.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.CREATE,
        user_id=actor_user_id,
        user_email=actor_user_email,
        resource_id=user.id,
        request=request,
        extra={"created_user_email": user.email, "role": role},
        commit=False,
    )
    await write_audit(
        db,
        resource_type=AuditResourceType.USER_ROLE,
        action=AuditAction.ROLE_ASSIGN,
        user_id=actor_user_id,
        user_email=actor_user_email,
        resource_id=user.id,
        request=request,
        extra={"target_user_id": user.id, "role": role},
        commit=False,
    )
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[tuple[User, list[str]]], int]:
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    offset = (page - 1) * page_size

    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    rows = await db.execute(
        select(User).order_by(User.id.desc()).offset(offset).limit(page_size)
    )
    users = list(rows.scalars().all())
    if not users:
        return [], total

    role_rows = await db.execute(
        select(UserRole.user_id, Role.code)
        .join(Role, Role.id == UserRole.role_id)
        .where(UserRole.user_id.in_([u.id for u in users]))
    )
    roles_by_user: dict[int, list[str]] = {}
    for uid, rcode in role_rows.all():
        roles_by_user.setdefault(uid, []).append(rcode)

    items = [(u, sorted(roles_by_user.get(u.id, []))) for u in users]
    return items, total
