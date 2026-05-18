"""启动时同步 Role / Permission / RolePermission 到数据库。

逻辑:
1. 权限点:新增 INSERT,name/module 变更 UPDATE,**配置中删除的不删数据库**(只警告)
2. 角色:种子角色不存在则插入(不覆盖已有 name/description)
3. role_permissions:不存在的 INSERT,配置已删除的 DELETE(完全镜像配置)
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.permission import Permission
from app.db.models.role import Role, RoleCode, RoleScope
from app.db.models.role_permission import RolePermission
from app.rbac.constants import PERMISSION_META, ROLE_META
from app.rbac.permissions_config import ROLE_PERMISSIONS

logger = logging.getLogger(__name__)


async def sync_rbac(db: AsyncSession) -> None:
    perms_added, perms_updated = await _sync_permissions(db)
    roles_added = await _sync_roles(db)
    rps_added, rps_removed = await _sync_role_permissions(db)
    await db.commit()
    logger.info(
        "RBAC sync done. Permissions: +%d new, %d updated. Roles: +%d new. "
        "RolePermissions: +%d / -%d.",
        perms_added, perms_updated, roles_added, rps_added, rps_removed,
    )


async def _sync_permissions(db: AsyncSession) -> tuple[int, int]:
    result = await db.execute(select(Permission))
    existing = {p.code: p for p in result.scalars().all()}
    configured_codes = set(PERMISSION_META.keys())

    added = updated = 0
    for code, meta in PERMISSION_META.items():
        if code not in existing:
            db.add(Permission(code=code, name=meta["name"], module=meta["module"]))
            added += 1
        else:
            p = existing[code]
            if p.name != meta["name"] or p.module != meta["module"]:
                p.name = meta["name"]
                p.module = meta["module"]
                updated += 1

    for code in existing.keys() - configured_codes:
        logger.warning("Permission %r exists in DB but not in config — kept (manual review).", code)

    await db.flush()
    return added, updated


async def _sync_roles(db: AsyncSession) -> int:
    result = await db.execute(select(Role))
    existing = {r.code: r for r in result.scalars().all()}
    added = 0
    for code in RoleCode.ALL:
        if code not in existing:
            meta = ROLE_META.get(code, {})
            db.add(Role(
                code=code,
                name=meta.get("name", code),
                scope=RoleScope.GLOBAL,
                description=meta.get("description"),
            ))
            added += 1
    await db.flush()
    return added


async def _sync_role_permissions(db: AsyncSession) -> tuple[int, int]:
    role_result = await db.execute(select(Role))
    roles_by_code = {r.code: r for r in role_result.scalars().all()}

    perm_result = await db.execute(select(Permission))
    perms_by_code = {p.code: p for p in perm_result.scalars().all()}

    rp_result = await db.execute(select(RolePermission))
    existing_rps = list(rp_result.scalars().all())
    existing_pairs = {(rp.role_id, rp.permission_id): rp for rp in existing_rps}

    desired_pairs: set[tuple[int, int]] = set()
    for role_code, perm_codes in ROLE_PERMISSIONS.items():
        role = roles_by_code.get(role_code)
        if role is None:
            logger.warning("Role %r not found during sync.", role_code)
            continue
        for pcode in perm_codes:
            perm = perms_by_code.get(pcode)
            if perm is None:
                logger.warning("Permission %r referenced by role %r missing.", pcode, role_code)
                continue
            desired_pairs.add((role.id, perm.id))

    added = removed = 0
    for pair in desired_pairs - existing_pairs.keys():
        db.add(RolePermission(role_id=pair[0], permission_id=pair[1]))
        added += 1
    for pair in existing_pairs.keys() - desired_pairs:
        await db.delete(existing_pairs[pair])
        removed += 1

    await db.flush()
    return added, removed
