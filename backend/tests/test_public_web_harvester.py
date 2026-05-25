"""PublicWebHarvester 字段映射单测(Δ7 Step 5)。mock Tavily + mock LLM。"""
from __future__ import annotations

import json

from app.services.credit.harvester.public_web_harvester import PublicWebHarvester
from tests._harvest_fakes import PROMPTS_ROOT, FakeLLM, FakeTavily, basic_json


def _harvester(tavily, llm) -> PublicWebHarvester:
    return PublicWebHarvester(tavily, llm, PROMPTS_ROOT)


async def test_harvest_basic_maps_fields():
    llm = FakeLLM(basic_json(
        established_date="2008-04-15",
        registered_capital="USD 50,000,000",
        _evidence={
            "established_date": "成立于2008年4月15日的工程公司",
            "registered_capital": "注册资本 USD 50,000,000 已实缴",
        },
        _confidence="high",
    ))
    h = _harvester(FakeTavily(), llm)
    r = await h.harvest_basic("ACME", "KH", "12345")

    assert r.status == "partial"  # 8 字段中 2 个有值
    assert r.data_source == "public"
    assert r.extracted["established_date"] == "2008-04-15"
    assert r.extracted["registered_capital"] == "USD 50,000,000"
    assert r.extracted["business_scope"] is None
    assert r.confidence == "high"
    assert r.tavily_calls == 1 and r.llm_calls == 1


async def test_harvest_basic_all_null_missing():
    h = _harvester(FakeTavily(), FakeLLM(basic_json()))
    r = await h.harvest_basic("ACME", "KH", None)
    assert r.status == "missing"
    assert r.data_source == "missing"


async def test_harvest_tavily_empty_missing_no_llm():
    llm = FakeLLM(basic_json())
    h = _harvester(FakeTavily(results=[]), llm)
    r = await h.harvest_basic("ACME", "KH", None)
    assert r.status == "missing"
    assert r.llm_calls == 0
    assert llm.calls == 0


async def test_harvest_qualifications_returns_list():
    qual = json.dumps({
        "has_iso_9001": True, "has_iso_14001": None, "has_iso_45001": None,
        "has_isc_certification": None, "other_certifications": [],
        "_evidence": {"has_iso_9001": "公司已通过 ISO 9001:2015 认证"},
        "_confidence": "medium",
    })
    h = _harvester(FakeTavily(), FakeLLM(qual))
    out = await h.harvest_qualifications("ACME", "KH", None)
    assert isinstance(out, list) and len(out) == 1
    assert out[0].extracted["has_iso_9001"] is True
    assert out[0].data_source == "public"


async def test_harvest_legal_media_source():
    legal = json.dumps({
        "litigation_count": None, "defaulter_unresolved_count": None,
        "defaulter_resolved_count": None, "negative_news_level": "occasional",
        "_evidence": {"negative_news_level": "媒体报道该公司偶有合同纠纷负面新闻"},
        "_confidence": "medium",
    })
    h = _harvester(FakeTavily(), FakeLLM(legal))
    r = await h.harvest_legal("ACME", "KH", None)
    assert r.status == "partial"
    assert r.data_source == "media"
    assert r.extracted["negative_news_level"] == "occasional"
