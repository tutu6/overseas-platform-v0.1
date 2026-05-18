"""RBAC 测试。"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.models.role import Role
from app.db.models.role_permission import RolePermission
from app.rbac.constants import Permissions
from app.rbac.permissions_config import ROLE_PERMISSIONS
from app.rbac.sync import sync_rbac

SUPER_PASS = settings.SUPER_ADMIN_INITIAL_PASSWORD
SUPER_EMAIL = settings.SUPER_ADMIN_EMAIL


async def _login(client, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"identifier": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _register_buyer(client, email="buyer1@cscec3b.com"):
    payload = {
        "email": email,
        "name": "Buyer 1",
        "phone": "13800138000",
        "password": "Abcd1234",
    }
    r = await client.post("/api/v1/auth/register/buyer", json=payload)
    assert r.status_code == 200, r.text
    return email, "Abcd1234"


async def _register_supplier(client, email="supplier1@huajian.com", license_no="LIC-001"):
    payload = {
        "email": email,
        "name": "Supplier 1",
        "phone": "13800138000",
        "password": "Abcd1234",
        "company_name": "Huajian Co",
        "business_license_no": license_no,
    }
    r = await client.post("/api/v1/auth/register/supplier", json=payload)
    assert r.status_code == 200, r.text
    return email, "Abcd1234"


async def _create_operator_via_super_admin(client, email="op1@platform.com"):
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "name": "OP 1",
            "password": "Abcd1234",
            "role": "OPERATOR",
            "must_change_password": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    return email, "Abcd1234"


@pytest.mark.asyncio
async def test_buyer_can_access_buyer_only(client):
    email, pwd = await _register_buyer(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/buyer-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_buyer_cannot_access_supplier_only(client):
    email, pwd = await _register_buyer(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/supplier-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_supplier_isolation(client):
    email, pwd = await _register_supplier(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/supplier-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = await client.get("/api/v1/test/buyer-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_access_admin_only(client):
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    r = await client.get("/api/v1/test/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_operator_can_access_operator_only(client):
    email, pwd = await _create_operator_via_super_admin(client)
    token = await _login(client, email, pwd)
    r = await client.get("/api/v1/test/operator-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    r = await client.get("/api/v1/test/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_create_buyer_role_rejected(client):
    """POST /admin/users 不应能创建 BUYER/SUPPLIER。"""
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "fakebuyer@x.com",
            "name": "X",
            "password": "Abcd1234",
            "role": "BUYER",
            "must_change_password": False,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422  # pydantic Literal 校验失败


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(client):
    b_email, b_pwd = await _register_buyer(client)
    token = await _login(client, b_email, b_pwd)
    r = await client.post(
        "/api/v1/admin/users",
        json={
            "email": "x@x.com",
            "name": "X",
            "password": "Abcd1234",
            "role": "OPERATOR",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_rbac_sync_restores_deleted_role_permission(client, db_session):
    """删除一条 role_permission 后重跑同步,应自动恢复。"""
    # 找一条 ADMIN-AUDIT_LOG_READ 关联,删掉
    admin = (await db_session.execute(select(Role).where(Role.code == "ADMIN"))).scalar_one()
    before = (await db_session.execute(
        select(RolePermission).where(RolePermission.role_id == admin.id)
    )).scalars().all()
    assert len(before) == len(ROLE_PERMISSIONS["ADMIN"])

    target = before[0]
    await db_session.delete(target)
    await db_session.commit()

    after_delete = (await db_session.execute(
        select(RolePermission).where(RolePermission.role_id == admin.id)
    )).scalars().all()
    assert len(after_delete) == len(ROLE_PERMISSIONS["ADMIN"]) - 1

    # 重跑同步
    await sync_rbac(db_session)
    restored = (await db_session.execute(
        select(RolePermission).where(RolePermission.role_id == admin.id)
    )).scalars().all()
    assert len(restored) == len(ROLE_PERMISSIONS["ADMIN"])


@pytest.mark.asyncio
async def test_me_permissions_match_config(client):
    """OPERATOR 的 permissions 应严格匹配配置。"""
    email, pwd = await _create_operator_via_super_admin(client)
    token = await _login(client, email, pwd)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    perms = set(me.json()["data"]["permissions"])
    assert perms == set(ROLE_PERMISSIONS["OPERATOR"])
    assert Permissions.USER_CREATE not in perms  # OPERATOR 没有创建用户权限
