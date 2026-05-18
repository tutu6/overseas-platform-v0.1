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


@pytest.mark.asyncio
async def test_business_permissions_isolated_per_role(client):
    """业务权限点严格隔离:BUYER 不应有 SUPPLIER 业务权限,反之亦然。"""
    # BUYER
    b_email, b_pwd = await _register_buyer(client)
    b_token = await _login(client, b_email, b_pwd)
    b_perms = set((await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {b_token}"}
    )).json()["data"]["permissions"])
    assert Permissions.PROJECT_READ in b_perms
    assert Permissions.RFQ_READ in b_perms
    assert Permissions.ORDER_READ in b_perms
    # 不应有
    assert Permissions.PRODUCT_READ not in b_perms       # 供应商商品
    assert Permissions.SUPPLIER_APPROVE not in b_perms   # 运营审核
    assert Permissions.SYSTEM_CONFIG not in b_perms      # 系统配置

    # SUPPLIER
    s_email, s_pwd = await _register_supplier(client)
    s_token = await _login(client, s_email, s_pwd)
    s_perms = set((await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {s_token}"}
    )).json()["data"]["permissions"])
    assert Permissions.PRODUCT_READ in s_perms
    assert Permissions.RFQ_RESPOND in s_perms
    assert Permissions.SUPPLIER_ORG_WRITE in s_perms
    assert Permissions.PROJECT_READ not in s_perms       # 采购方项目
    assert Permissions.OPERATOR_DASHBOARD_READ not in s_perms


@pytest.mark.asyncio
async def test_admin_has_system_config_but_no_business(client):
    """ADMIN 严格不触业务数据(Q25)— 只有系统/RBAC 权限,无业务权限。"""
    token = await _login(client, SUPER_EMAIL, SUPER_PASS)
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    perms = set(me.json()["data"]["permissions"])
    assert Permissions.SYSTEM_CONFIG in perms
    assert Permissions.USER_CREATE in perms
    # 业务权限点不应有
    for p in [Permissions.PROJECT_READ, Permissions.PRODUCT_READ, Permissions.RFQ_READ,
              Permissions.ORDER_READ, Permissions.SUPPLIER_APPROVE, Permissions.RISK_READ]:
        assert p not in perms, f"ADMIN 不应有业务权限 {p}"
