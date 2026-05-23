"""信用评估接口的 RBAC scope 测试。

覆盖:
- ADMIN 不持有任何 credit:* → 调任意 credit 接口均 403
- SUPPLIER 持有 credit:read 但 scope=OWN → 看不到 linked_supplier_org_id 不匹配的企业
- BUYER / OPERATOR scope=ALL → 行为不变
- SUPPLIER 在自家 company(linked_supplier_org_id 匹配)上仍可正常 read
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models import CreditCompany
from app.db.models.supplier_member import SupplierMember
from app.db.models.supplier_organization import SupplierOrganization


# -------- 登录工具 --------

async def _login(client, email, password) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def _admin_token(client) -> str:
    return await _login(client, "admin@platform.local", "Aa123456789")


async def _operator_token(client) -> str:
    return await _login(client, "operator@platform.local", "Aa123456789")


async def _buyer_token(client) -> str:
    return await _login(client, "buyer@cscec3b.local", "Aa123456789")


async def _register_supplier(client, email, phone, company_name) -> str:
    r = await client.post(
        "/api/v1/auth/register/supplier",
        json={
            "email": email, "name": "S", "phone": phone,
            "password": "Aa123456789", "company_name": company_name,
            "country_code": "CN", "registration_no": "SC-CR-1",
            "language_preference": "zh",
        },
    )
    assert r.status_code in (200, 201), r.text
    return await _login(client, email, "Aa123456789")


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


# -------- ADMIN 全部 credit 接口 403 --------

@pytest.mark.asyncio
async def test_admin_search_403(client):
    t = await _admin_token(client)
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_detail_403(client):
    t = await _admin_token(client)
    r = await client.get("/api/v1/credit/companies/1", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_recompute_403(client):
    t = await _admin_token(client)
    r = await client.post("/api/v1/credit/companies/1/recompute", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_recompute_all_403(client):
    t = await _admin_token(client)
    r = await client.post("/api/v1/credit/recompute-all", headers=_auth(t))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_admin_ai_conversation_403(client):
    t = await _admin_token(client)
    r = await client.post(
        "/api/v1/credit/ai/conversations", json={"company_id": 1}, headers=_auth(t)
    )
    assert r.status_code == 403


# -------- BUYER / OPERATOR scope=ALL 行为不变 --------

@pytest.mark.asyncio
async def test_buyer_search_sees_demo_companies(client):
    t = await _buyer_token(client)
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 200
    items = r.json()["data"]
    # seed_credit 入 4 家 demo
    assert len(items) >= 1


@pytest.mark.asyncio
async def test_operator_search_sees_demo_companies(client):
    t = await _operator_token(client)
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 200
    assert len(r.json()["data"]) >= 1


# -------- SUPPLIER scope=OWN --------

@pytest.mark.asyncio
async def test_supplier_search_empty_when_no_linked_company(client):
    """SUPPLIER 注册后无任何 credit_company 关联 → 列表为空(scope=OWN 强制过滤)。"""
    t = await _register_supplier(client, "sup.credit1@x.com", "13900139601", "S Credit 1")
    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 200
    assert r.json()["data"] == []


@pytest.mark.asyncio
async def test_supplier_detail_404_when_not_linked(client, test_engine):
    """SUPPLIER 访问任意 demo 企业详情 → 404(linked_supplier_org_id 不匹配)。
    文案与"真不存在"一致,不暴露存在性。
    """
    t = await _register_supplier(client, "sup.credit2@x.com", "13900139602", "S Credit 2")
    # 找一个已存在的 demo 企业 id
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = (await db.execute(select(CreditCompany.id).limit(1))).scalar_one()
    r = await client.get(f"/api/v1/credit/companies/{cid}", headers=_auth(t))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_supplier_ai_create_404_when_not_linked(client, test_engine):
    t = await _register_supplier(client, "sup.credit3@x.com", "13900139603", "S Credit 3")
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        cid = (await db.execute(select(CreditCompany.id).limit(1))).scalar_one()
    r = await client.post(
        "/api/v1/credit/ai/conversations", json={"company_id": cid}, headers=_auth(t)
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_supplier_search_sees_own_linked_company(client, test_engine):
    """positive path:SUPPLIER 的 supplier_org 与某 company 的 linked_supplier_org_id 匹配 → 看得见。"""
    t = await _register_supplier(client, "sup.credit4@x.com", "13900139604", "S Credit 4")

    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        # 取 SUPPLIER 的 supplier_org_id
        row = await db.execute(
            select(SupplierMember.supplier_org_id).join(
                SupplierOrganization, SupplierOrganization.id == SupplierMember.supplier_org_id
            ).where(SupplierOrganization.name == "S Credit 4")
        )
        sup_org_id = row.scalar_one()
        # 给一家 demo 企业贴上 linked_supplier_org_id
        comp = (await db.execute(select(CreditCompany).limit(1))).scalar_one()
        comp.linked_supplier_org_id = sup_org_id
        await db.commit()
        linked_id = comp.id

    r = await client.get("/api/v1/credit/companies/search?country=&q=", headers=_auth(t))
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == linked_id

    # 详情也能看
    r2 = await client.get(f"/api/v1/credit/companies/{linked_id}", headers=_auth(t))
    assert r2.status_code == 200
