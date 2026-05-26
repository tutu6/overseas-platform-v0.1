"""业务编排:并发调 4 路(工商/司法 × Tavily/爬虫),单路失败兜底不拖全场。"""
from __future__ import annotations

import asyncio
import time
from datetime import date

from cache import get_cache
from data_sources.crawlers.khmer_times import KhmerTimesCrawler
from data_sources.crawlers.moc_cambodia import MocCambodiaCrawler
from data_sources.crawlers.phnom_penh_post import PhnomPenhPostCrawler
from data_sources.tavily_llm.basic_extractor import extract_basic_via_tavily_llm
from data_sources.tavily_llm.legal_extractor import extract_legal_via_tavily_llm
from schemas import (
    BasicFields,
    BasicResult,
    ComparisonResponse,
    LegalResult,
    LegalResultWithOverlap,
    OverlapAnalysis,
)


async def crawl_basic_via_moc(company_name: str) -> BasicResult:
    return await MocCambodiaCrawler().fetch(company_name)


async def crawl_legal_via_media(company_name: str) -> LegalResult:
    """并发两媒体爬虫,合并 + 负面统计;403 → blocked。"""
    start = time.time()
    crawlers = [PhnomPenhPostCrawler(), KhmerTimesCrawler()]
    results = await asyncio.gather(
        *[c.fetch(company_name) for c in crawlers], return_exceptions=True
    )
    articles = []
    errors = []
    blocked = False
    for c, r in zip(crawlers, results):
        if isinstance(r, Exception):
            errors.append(f"{c.SOURCE_NAME}: {r}")
            if "403" in str(r) or "401" in str(r):
                blocked = True
        else:
            articles.extend(r)
    articles.sort(key=lambda a: a.published_date or date.min, reverse=True)
    neg = sum(1 for a in articles if a.is_negative)
    latest = next((a.published_date for a in articles if a.published_date), None)
    if articles:
        status = "ok"
    elif blocked:
        status = "access_restricted"
    elif errors:
        status = "error"
    else:
        status = "no_match"
    return LegalResult(
        source="crawler_media", status=status, article_count=len(articles),
        negative_count=neg, latest_published=latest, articles=articles,
        duration_ms=int((time.time() - start) * 1000),
        error_detail="; ".join(errors)[:300] if errors else None,
    )


def _wrap_basic(res, source: str) -> BasicResult:
    if isinstance(res, Exception):
        return BasicResult(source=source, status="error", fields=BasicFields(),
                           fields_filled=0, duration_ms=0, error_detail=str(res)[:300])
    return res


def _wrap_legal(res, source: str) -> LegalResult:
    if isinstance(res, Exception):
        return LegalResult(source=source, status="error", article_count=0,
                           negative_count=0, latest_published=None, articles=[],
                           duration_ms=0, error_detail=str(res)[:300])
    return res


def calc_overlap(tavily_articles, crawler_articles) -> OverlapAnalysis:
    """两路召回 URL 重合度(v1.1)。"""
    t = {a.url for a in tavily_articles if a.url}
    c = {a.url for a in crawler_articles if a.url}
    return OverlapAnalysis(
        tavily_total=len(t),
        crawler_total=len(c),
        overlap_count=len(t & c),
        overlap_urls=sorted(t & c),
        tavily_only_urls=sorted(t - c),
        crawler_only_urls=sorted(c - t),
    )


async def compare_company(company_name: str, force_refresh: bool = False) -> ComparisonResponse:
    """4 路并发对照。"""
    if force_refresh:
        get_cache().clear_company(company_name)

    bt, bc, lt, lc = await asyncio.gather(
        extract_basic_via_tavily_llm(company_name),
        crawl_basic_via_moc(company_name),
        extract_legal_via_tavily_llm(company_name),
        crawl_legal_via_media(company_name),
        return_exceptions=True,
    )
    legal_t = _wrap_legal(lt, "tavily_llm")
    legal_c = _wrap_legal(lc, "crawler_media")
    return ComparisonResponse(
        company_name=company_name,
        basic_tavily=_wrap_basic(bt, "tavily_llm"),
        basic_crawler=_wrap_basic(bc, "crawler_moc"),
        legal=LegalResultWithOverlap(
            legal_tavily=legal_t,
            legal_crawler=legal_c,
            overlap=calc_overlap(legal_t.articles, legal_c.articles),
        ),
    )
