"""启动种子。

- 中建三局 BuyerOrganization(code=CSCEC3B)
- 初始 super admin(env 注入,must_change_password=true,绝不覆盖已有)
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.constants import AuditAction, AuditResourceType
from app.audit.logger import write_audit
from app.core.config import settings
from app.core.security import hash_password
from app.db.models.buyer_organization import BuyerOrganization, BuyerOrgStatus
from app.db.models.role import Role, RoleCode
from app.db.models.user import User, UserStatus
from app.db.models.user_role import UserRole
from app.services.auth_service import CSCEC3B_CODE

logger = logging.getLogger(__name__)


async def seed_buyer_org(db: AsyncSession) -> None:
    row = await db.execute(
        select(BuyerOrganization).where(BuyerOrganization.code == CSCEC3B_CODE)
    )
    if row.scalar_one_or_none() is not None:
        return
    db.add(BuyerOrganization(
        name="中建三局",
        code=CSCEC3B_CODE,
        description="中国建筑第三工程局有限公司(MVP 唯一业主方)",
        status=BuyerOrgStatus.ACTIVE,
    ))
    await db.commit()
    logger.info("Seed: BuyerOrganization '中建三局' created.")


async def _seed_internal_account(
    db: AsyncSession,
    *,
    email: str,
    username: str,
    name: str,
    password: str,
    role_code: str,
) -> None:
    """通用:创建一个内部账号(若已存在 email 或 username 则跳过)。"""
    row = await db.execute(
        select(User).where((User.email == email) | (User.username == username))
    )
    if row.scalar_one_or_none() is not None:
        logger.info("Seed: demo internal account %s already exists — kept as-is.", email)
        return

    role_row = await db.execute(select(Role).where(Role.code == role_code))
    role = role_row.scalar_one_or_none()
    if role is None:
        logger.error("Seed: %s role missing, did rbac sync run first?", role_code)
        return

    user = User(
        email=email,
        username=username,
        name=name,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        must_change_password=False,  # demo 账号,跳过强制改密以方便体验
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        extra={"reason": "seed_demo_internal", "role": role_code},
        commit=False,
    )
    await db.commit()
    logger.warning(
        "Seed: demo %s account created — email=%s username=%s. "
        "**仅用于开发演示,生产环境务必删除或改密**",
        role_code, email, username,
    )


async def seed_demo_internal_accounts(db: AsyncSession) -> None:
    """创建 demo ADMIN / OPERATOR 各一个,方便快速进各工作台体验。"""
    await _seed_internal_account(
        db,
        email="admin@platform.local",
        username="admin",
        name="演示管理员",
        password="12345678a",
        role_code=RoleCode.ADMIN,
    )
    await _seed_internal_account(
        db,
        email="operator@platform.local",
        username="operator",
        name="演示运营",
        password="12345678a",
        role_code=RoleCode.OPERATOR,
    )


async def seed_super_admin(db: AsyncSession) -> None:
    email = settings.SUPER_ADMIN_EMAIL
    row = await db.execute(select(User).where(User.email == email))
    if row.scalar_one_or_none() is not None:
        logger.info("Seed: super admin %s already exists — kept as-is.", email)
        return

    role_row = await db.execute(select(Role).where(Role.code == RoleCode.ADMIN))
    admin_role = role_row.scalar_one_or_none()
    if admin_role is None:
        logger.error("Seed: ADMIN role missing, did rbac sync run first?")
        return

    user = User(
        email=email,
        name="Super Admin",
        password_hash=hash_password(settings.SUPER_ADMIN_INITIAL_PASSWORD),
        status=UserStatus.ACTIVE,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    db.add(UserRole(user_id=user.id, role_id=admin_role.id))

    await write_audit(
        db,
        resource_type=AuditResourceType.USER,
        action=AuditAction.REGISTER,
        user_id=user.id,
        user_email=user.email,
        resource_id=user.id,
        extra={"reason": "seed_super_admin", "role": RoleCode.ADMIN},
        commit=False,
    )
    await db.commit()
    logger.warning(
        "Seed: super admin %s created with initial password from env. "
        "**MUST change password on first login**.",
        email,
    )


async def run_all_seeds(db: AsyncSession) -> None:
    await seed_buyer_org(db)
    await seed_super_admin(db)
    await seed_demo_internal_accounts(db)
