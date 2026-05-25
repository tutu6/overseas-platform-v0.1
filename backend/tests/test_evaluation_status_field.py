"""详情接口 evaluation_status 三态判定(Δ7 Step 13)。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.v1.credit import _evaluation_status
from app.db.models import CreditCompany, CreditDataHarvestRun


async def test_eval_status_states(test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        # 非 KH → 恒 ready
        cn = CreditCompany(name="CN", country_code="CN")
        db.add(cn)
        await db.flush()
        st, latest = await _evaluation_status(db, cn)
        assert st == "ready" and latest is None

        # KH 无 run → pending(防御)
        kh = CreditCompany(name="KH", country_code="KH")
        db.add(kh)
        await db.flush()
        st, latest = await _evaluation_status(db, kh)
        assert st == "pending" and latest is None

        # running → pending
        db.add(CreditDataHarvestRun(
            company_id=kh.id, status="running", triggered_by="manual",
            started_at=datetime(2026, 5, 25),
        ))
        await db.flush()
        st, _ = await _evaluation_status(db, kh)
        assert st == "pending"

        # 更晚的 succeeded → ready(取最近一条)
        db.add(CreditDataHarvestRun(
            company_id=kh.id, status="succeeded", triggered_by="manual",
            started_at=datetime(2026, 5, 26),
        ))
        await db.flush()
        st, latest = await _evaluation_status(db, kh)
        assert st == "ready"
        assert latest["status"] == "succeeded"

        # 更晚的 failed → failed
        db.add(CreditDataHarvestRun(
            company_id=kh.id, status="failed", triggered_by="manual",
            started_at=datetime(2026, 5, 27),
        ))
        await db.flush()
        st, _ = await _evaluation_status(db, kh)
        assert st == "failed"

        # cached_hit → ready
        db.add(CreditDataHarvestRun(
            company_id=kh.id, status="cached_hit", triggered_by="manual",
            started_at=datetime(2026, 5, 28),
        ))
        await db.flush()
        st, _ = await _evaluation_status(db, kh)
        assert st == "ready"


async def _operator_token(client) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


async def test_detail_endpoint_returns_evaluation_status(client, test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        kh = CreditCompany(name="KH Detail", country_code="KH", registration_no="KH-D-1")
        db.add(kh)
        await db.flush()
        db.add(CreditDataHarvestRun(
            company_id=kh.id, status="running", triggered_by="supplier_register",
            started_at=datetime(2026, 5, 25),
        ))
        cid = kh.id
        await db.commit()

    t = await _operator_token(client)
    r = await client.get(f"/api/v1/credit/companies/{cid}", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["evaluation_status"] == "pending"
    assert data["latest_harvest_run"]["status"] == "running"
