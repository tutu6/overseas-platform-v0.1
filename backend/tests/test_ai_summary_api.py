"""Δ8:AI 评语按需触发接口 POST /credit/companies/{id}/ai-summary/generate。

验收点 #7-10:
- 无 current snapshot → 400
- 已生成过 → cached=true,不调 LLM
- 未生成 → 调 LLM 并回写,cached=false
- LLM 失败(generate_for_snapshot 返回 None)→ 503
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

import app.api.v1.credit as credit_api
from app.db.base import _utcnow
from app.db.models import CreditCompany, ScoreSnapshot, TriggerType


async def _operator_token(client) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "operator@platform.local", "password": "Aa123456789"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _auth(t: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {t}"}


async def _make_company(test_engine, *, with_snapshot: bool, ai_summary: str | None = None) -> int:
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)
    async with SessionLocal() as db:
        c = CreditCompany(name=f"KH AISum {datetime.now().timestamp()}", country_code="KH")
        db.add(c)
        await db.flush()
        if with_snapshot:
            db.add(ScoreSnapshot(
                company_id=c.id, total_score=80, grade="B",
                dimension_1_score=20, dimension_2_score=20,
                dimension_3_score=20, dimension_4_score=20,
                rule_version=1, trigger_type=TriggerType.REAL_TIME_ONBOARD,
                is_current=True, calculated_at=_utcnow(),
                ai_summary=ai_summary,
                ai_summary_generated_at=_utcnow() if ai_summary else None,
            ))
        cid = c.id
        await db.commit()
    return cid


@pytest.mark.asyncio
async def test_no_snapshot_returns_400(client, test_engine):
    cid = await _make_company(test_engine, with_snapshot=False)
    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_already_generated_returns_cached(client, test_engine, monkeypatch):
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary="已有评语")

    # 已生成应直接返回缓存,不得调 LLM:patch 成抛错,若被调到则测试失败
    async def _must_not_call(self, session, snapshot_id):  # noqa: ANN001
        raise AssertionError("已生成场景不应调用 LLM")

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _must_not_call)

    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["cached"] is True
    assert data["ai_summary"] == "已有评语"


@pytest.mark.asyncio
async def test_first_generation_calls_llm(client, test_engine, monkeypatch):
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary=None)

    async def _fake_generate(self, session, snapshot_id):  # noqa: ANN001
        snap = await session.get(ScoreSnapshot, snapshot_id)
        snap.ai_summary = "新生成评语"
        snap.ai_summary_generated_at = _utcnow()
        return "新生成评语"

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _fake_generate)

    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["cached"] is False
    assert data["ai_summary"] == "新生成评语"


@pytest.mark.asyncio
async def test_llm_failure_returns_503(client, test_engine, monkeypatch):
    cid = await _make_company(test_engine, with_snapshot=True, ai_summary=None)

    async def _fake_fail(self, session, snapshot_id):  # noqa: ANN001
        return None  # generate_for_snapshot 内部吞错后返回 None

    monkeypatch.setattr(credit_api.AISummaryGenerator, "generate_for_snapshot", _fake_fail)

    t = await _operator_token(client)
    r = await client.post(
        f"/api/v1/credit/companies/{cid}/ai-summary/generate", headers=_auth(t)
    )
    assert r.status_code == 503, r.text
