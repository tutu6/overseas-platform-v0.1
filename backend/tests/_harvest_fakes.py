"""Δ7 harvester 测试共享 fake(下划线前缀,pytest 不收集为测试)。"""
from __future__ import annotations

import json
from pathlib import Path

from app.services.credit.harvester import public_web_harvester as _pwh
from app.services.credit.harvester.public_web_harvester import HarvestResult
from app.services.credit.harvester.tavily_client import TavilyError, TavilySearchResult
from app.services.llm.base import LLMUnavailableError

PROMPTS_ROOT = Path(_pwh.__file__).parent / "prompts"


def make_result(status="ok", data_source="public", extracted=None, *, evidence=None, error=None):
    """构造 HarvestResult(harvest_task 集成测试用)。"""
    return HarvestResult(
        status=status,
        data_source=data_source,
        extracted=extracted or {},
        raw_llm_response="{}",
        evidence=evidence or {},
        confidence="high",
        tavily_calls=0 if status == "failed" else 1,
        llm_calls=0 if status == "failed" else 1,
        tavily_results=[{"url": "https://x", "title": "t", "content": "c"}],
        error=error,
    )


class FakeHarvester:
    """直接返回预设 HarvestResult,绕过 Tavily/LLM。"""

    def __init__(self, basic, finance, legal, qual):
        self._b, self._f, self._l, self._q = basic, finance, legal, qual

    async def harvest_basic(self, *a, **k):
        return self._b

    async def harvest_finance(self, *a, **k):
        return self._f

    async def harvest_legal(self, *a, **k):
        return self._l

    async def harvest_qualifications(self, *a, **k):
        return [self._q]


class RaisingHarvester:
    """任何方法被调用即失败 — 验证缓存命中路径不触发抓取。"""

    async def harvest_basic(self, *a, **k):
        raise AssertionError("harvester 不应在缓存命中时被调用")

    harvest_finance = harvest_basic
    harvest_legal = harvest_basic
    harvest_qualifications = harvest_basic


class FakeTavily:
    def __init__(self, results=None, raise_error=False):
        self._results = (
            results
            if results is not None
            else [TavilySearchResult(title="t", url="https://x", content="some context text")]
        )
        self._raise = raise_error

    async def search(self, query, max_results=5, **kw):
        if self._raise:
            raise TavilyError("boom")
        return self._results


class FakeLLM:
    def __init__(self, response="{}", raise_error=False):
        self._response = response
        self._raise = raise_error
        self.calls = 0

    async def generate_json(self, prompt, *, timeout_seconds=None):
        self.calls += 1
        if self._raise:
            raise LLMUnavailableError("down")
        return self._response


def basic_json(**overrides) -> str:
    """构造 basic 维度 LLM 应答 JSON;默认全 null,用 kwargs 覆盖字段或 _evidence。"""
    payload = {
        "established_date": None, "registered_capital": None, "business_scope": None,
        "legal_representative": None, "shareholders": None, "status_text": None,
        "address": None, "website": None, "_evidence": {}, "_confidence": "low",
    }
    payload.update(overrides)
    return json.dumps(payload)
