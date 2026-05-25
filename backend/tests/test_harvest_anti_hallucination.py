"""反幻觉后处理单测(Δ7 §4.1)。无有效 source_quote 的字段强制置 null。"""
from __future__ import annotations

from app.services.credit.harvester.public_web_harvester import PublicWebHarvester
from tests._harvest_fakes import PROMPTS_ROOT, FakeLLM, FakeTavily, basic_json


def _h(llm) -> PublicWebHarvester:
    return PublicWebHarvester(FakeTavily(), llm, PROMPTS_ROOT)


async def test_field_without_evidence_forced_null():
    # established_date 有值但 _evidence 完全缺失 → 后处理置 null
    llm = FakeLLM(basic_json(established_date="2010-01-01", _evidence={}))
    r = await _h(llm).harvest_basic("A", "KH", None)
    assert r.extracted["established_date"] is None
    assert r.status == "missing"


async def test_short_quote_forced_null():
    # quote < 10 字符 → 无效 → 置 null
    llm = FakeLLM(basic_json(
        established_date="2010-01-01",
        _evidence={"established_date": "短引用"},
    ))
    r = await _h(llm).harvest_basic("A", "KH", None)
    assert r.extracted["established_date"] is None


async def test_valid_quote_kept():
    llm = FakeLLM(basic_json(
        established_date="2010-01-01",
        _evidence={"established_date": "公司于2010年1月1日正式注册成立"},
    ))
    r = await _h(llm).harvest_basic("A", "KH", None)
    assert r.extracted["established_date"] == "2010-01-01"


async def test_llm_failure_retries_then_failed():
    llm = FakeLLM(raise_error=True)
    r = await _h(llm).harvest_basic("A", "KH", None)
    assert r.status == "failed"
    assert llm.calls == 2  # 1 + retry(1)
    assert r.llm_calls == 2


async def test_invalid_json_failed():
    llm = FakeLLM("这不是JSON")
    r = await _h(llm).harvest_basic("A", "KH", None)
    assert r.status == "failed"
    assert r.error and "schema" in r.error
