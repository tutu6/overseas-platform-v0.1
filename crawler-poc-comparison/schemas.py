"""Pydantic 模型(字段对齐 PRD §Δ10)。"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


# ---------- 工商基础 ----------

class BasicFields(BaseModel):
    """工商基础字段(对齐 PRD §Δ10,7 字段)。"""
    company_full_name: str | None = None
    country_region: str | None = None
    registration_no: str | None = None
    established_date: date | None = None
    legal_representative: str | None = None
    business_scope: str | None = None
    registered_capital: str | None = None


class BasicResult(BaseModel):
    """工商基础单源结果。"""
    source: str  # tavily_llm / crawler_moc
    # success / partial / blocked / not_found / parse_failed / timeout / error
    status: str
    fields: BasicFields
    fields_filled: int
    fields_total: int = 7
    source_url: str | None = None
    duration_ms: int
    cache_hit: bool = False
    error_detail: str | None = None
    raw_snippet: str | None = None  # 失败现场(HTML 片段或 LLM 应答前 500 字)


# ---------- 司法舆情 ----------

class LegalArticle(BaseModel):
    source_site: str  # phnompenhpost / khmertimes / tavily_llm
    title: str
    url: str
    published_date: date | None = None
    snippet: str
    is_negative: bool


class LegalResult(BaseModel):
    """司法舆情单源结果。"""
    source: str  # tavily_llm / crawler_media
    status: str
    article_count: int
    negative_count: int
    latest_published: date | None
    articles: list[LegalArticle]
    duration_ms: int
    cache_hit: bool = False
    error_detail: str | None = None


# ---------- 顶层响应 ----------

class ComparisonResponse(BaseModel):
    """页面查询的顶层响应(4 路并发结果)。"""
    company_name: str
    basic_tavily: BasicResult
    basic_crawler: BasicResult
    legal_tavily: LegalResult
    legal_crawler: LegalResult
