"""通用公开网络数据抓取(Δ7 Step 5)。

Tavily 搜索 + LLM 结构化抽取 + 反幻觉后处理。国别无关,按 country_code 选 prompt 模板。
落库 / 触发评分由 harvest_task 负责,本类只产出结构化 HarvestResult。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from app.services.credit.harvester.schemas import (
    BasicExtractedSchema,
    CertificationExtractedSchema,
    FinanceExtractedSchema,
    LegalExtractedSchema,
)
from app.services.credit.harvester.tavily_client import TavilyClient, TavilyError
from app.services.llm.base import LLMService, LLMUnavailableError

logger = logging.getLogger(__name__)

# 反幻觉:source_quote 最小有效长度(< 此长度视为无效引用)
MIN_QUOTE_LEN = 10

# 国别 ISO-2 → 英文名(拼搜索 query 用)
COUNTRY_NAMES: dict[str, str] = {"KH": "Cambodia"}

# 各维度参与"反幻觉 null 化"的数据字段(不含 evidence/confidence/notes 元字段)
_DATA_FIELDS: dict[str, list[str]] = {
    "basic": [
        "established_date", "registered_capital", "business_scope",
        "legal_representative", "shareholders", "status_text", "address", "website",
    ],
    "finance": ["revenue_trend", "debt_ratio", "cash_flow_status"],
    "legal": [
        "litigation_count", "defaulter_unresolved_count",
        "defaulter_resolved_count", "negative_news_level",
    ],
    "qualification": [
        "has_iso_9001", "has_iso_14001", "has_iso_45001",
        "has_isc_certification", "other_certifications",
    ],
}

# 维度主数据来源标记(status != missing 时用;§4.2)
_DIMENSION_SOURCE: dict[str, str] = {
    "basic": "public",
    "finance": "public",
    "legal": "media",
    "qualification": "public",
}


class HarvestResult(BaseModel):
    """单维度抓取结果。"""
    status: str  # ok / partial / missing / failed
    data_source: str  # public / media / missing
    extracted: dict[str, Any]
    raw_llm_response: str
    evidence: dict[str, str | None]
    confidence: str | None
    tavily_calls: int
    llm_calls: int
    tavily_results: list[dict[str, Any]] = []  # Tavily 原始结果,落 raw_data 留存
    error: str | None = None


def _has_value(v: Any) -> bool:
    """None / 空字符串 / 空列表 视为"无值"。"""
    if v is None:
        return False
    if isinstance(v, (list, str)) and len(v) == 0:
        return False
    return True


def _apply_anti_hallucination(
    extracted: dict[str, Any],
    evidence: dict[str, str | None],
    data_fields: list[str],
) -> dict[str, Any]:
    """反幻觉:无有效 source_quote(缺失 / 空 / <10 字符)的字段强制置 null。"""
    cleaned = dict(extracted)
    for f in data_fields:
        if not _has_value(cleaned.get(f)):
            continue
        quote = evidence.get(f)
        if not isinstance(quote, str) or len(quote.strip()) < MIN_QUOTE_LEN:
            # list 字段置空数组,其余置 None
            cleaned[f] = [] if isinstance(cleaned.get(f), list) else None
    return cleaned


def _judge_status(cleaned: dict[str, Any], data_fields: list[str]) -> str:
    non_null = [f for f in data_fields if _has_value(cleaned.get(f))]
    if not non_null:
        return "missing"
    if len(non_null) < len(data_fields):
        return "partial"
    return "ok"


class PublicWebHarvester:
    """通用工具:Tavily 搜索 + qwen-plus 结构化抽取 + 反幻觉。"""

    def __init__(
        self,
        tavily: TavilyClient,
        llm: LLMService,
        prompts_root: Path,
        *,
        max_results: int = 5,
        llm_timeout_seconds: int = 30,
        llm_retry: int = 1,
    ) -> None:
        self._tavily = tavily
        self._llm = llm
        self._prompts_root = Path(prompts_root)
        self._max_results = max_results
        self._llm_timeout = llm_timeout_seconds
        self._llm_retry = llm_retry

    # ---- 公开维度入口 ----
    async def harvest_basic(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> HarvestResult:
        q = f'"{company_name}" {registration_no or ""} {self._country(country_code)} company registration'
        return await self._harvest(
            "basic", q, BasicExtractedSchema, company_name, registration_no, country_code
        )

    async def harvest_finance(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> HarvestResult:
        q = f'"{company_name}" {self._country(country_code)} annual report revenue financial'
        return await self._harvest(
            "finance", q, FinanceExtractedSchema, company_name, registration_no, country_code
        )

    async def harvest_legal(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> HarvestResult:
        q = f'"{company_name}" {self._country(country_code)} lawsuit court litigation'
        return await self._harvest(
            "legal", q, LegalExtractedSchema, company_name, registration_no, country_code
        )

    async def harvest_qualifications(
        self, company_name: str, country_code: str, registration_no: str | None
    ) -> list[HarvestResult]:
        # 证书维度本期单次抽取"是否拥有"类布尔;返回 list 以兼容未来多证书拆分
        q = f'"{company_name}" {self._country(country_code)} ISO certification standard'
        result = await self._harvest(
            "qualification", q, CertificationExtractedSchema,
            company_name, registration_no, country_code,
        )
        return [result]

    # ---- 内部 ----
    def _country(self, code: str) -> str:
        return COUNTRY_NAMES.get(code.upper(), code)

    def _load_prompt(self, country_code: str, dimension: str) -> str:
        path = self._prompts_root / country_code.lower() / f"{dimension}.txt"
        return path.read_text(encoding="utf-8")

    async def _harvest(
        self,
        dimension: str,
        query: str,
        schema_cls: type[BaseModel],
        company_name: str,
        registration_no: str | None,
        country_code: str,
    ) -> HarvestResult:
        # 1. Tavily 搜索
        try:
            results = await self._tavily.search(query, max_results=self._max_results)
        except TavilyError as exc:
            logger.warning("[harvest:%s] Tavily 失败: %s", dimension, exc)
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=0, llm_calls=0, error=f"tavily: {exc}",
            )
        if not results:
            return HarvestResult(
                status="missing", data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=1, llm_calls=0,
            )
        search_context = "\n\n".join(
            f"[{r.title}] {r.url}\n{r.content}" for r in results
        )

        # 2. 加载 prompt 模板并替换占位
        try:
            template = self._load_prompt(country_code, dimension)
        except OSError as exc:
            logger.error("[harvest:%s] prompt 模板缺失: %s", dimension, exc)
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=1, llm_calls=0, error=f"prompt: {exc}",
            )
        prompt = (
            template.replace("{company_name}", company_name)
            .replace("{registration_no}", registration_no or "")
            .replace("{search_context}", search_context)
        )

        # 3. LLM 结构化抽取(失败重试 llm_retry 次)
        raw: str | None = None
        last_err: Exception | None = None
        llm_calls = 0
        for _ in range(1 + self._llm_retry):
            try:
                raw = await self._llm.generate_json(
                    prompt, timeout_seconds=self._llm_timeout
                )
                llm_calls += 1
                break
            except LLMUnavailableError as exc:
                last_err = exc
                llm_calls += 1
        if raw is None:
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response="", evidence={}, confidence=None,
                tavily_calls=1, llm_calls=llm_calls, error=f"llm: {last_err}",
            )

        # 4. JSON + schema 校验
        try:
            model = schema_cls.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("[harvest:%s] JSON/schema 校验失败: %s", dimension, exc)
            return HarvestResult(
                status="failed", data_source="missing", extracted={},
                raw_llm_response=raw, evidence={}, confidence=None,
                tavily_calls=1, llm_calls=llm_calls, error=f"schema: {exc}",
            )

        # 5. 反幻觉后处理 + 状态判定
        data_fields = _DATA_FIELDS[dimension]
        extracted = model.model_dump(exclude={"evidence", "confidence", "notes"})
        evidence: dict[str, str | None] = getattr(model, "evidence", {}) or {}
        cleaned = _apply_anti_hallucination(extracted, evidence, data_fields)
        status = _judge_status(cleaned, data_fields)
        data_source = "missing" if status == "missing" else _DIMENSION_SOURCE[dimension]
        return HarvestResult(
            status=status,
            data_source=data_source,
            extracted=cleaned,
            raw_llm_response=raw,
            evidence=evidence,
            confidence=getattr(model, "confidence", None),
            tavily_calls=1,
            llm_calls=llm_calls,
            tavily_results=[r.model_dump() for r in results],
        )
