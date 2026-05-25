"""抓取任务编排(Δ7 Step 10/11/12)。

run_harvest_for_company:完整抓取流程(缓存检查 → 写 run → 四维度抓取 → 落快照
→ 更新 run → 触发评分),调用方负责事务提交。
harvest_after_register / manual_harvest:BackgroundTask 入口,各用独立 session,
失败只记日志不抛(不影响主流程)。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.context import get_trace_id
from app.core.config import settings
from app.db.base import _utcnow
from app.db.models import (
    AuditLog,
    CertStatus,
    CertType,
    CreditCompany,
    CreditCompanyBasicData,
    CreditCompanyCertification,
    CreditCompanyFinanceData,
    CreditCompanyLegalData,
    CreditDataHarvestRun,
    HarvestRunStatus,
    HarvestTriggeredBy,
    ScoreSnapshot,
    TriggerType,
)
from app.db.session import AsyncSessionLocal
from app.services.credit.data_source.registry import resolve_data_source
from app.services.credit.errors import CompanyNotFoundError
from app.services.credit.harvester.public_web_harvester import (
    HarvestResult,
    PublicWebHarvester,
)
from app.services.credit.harvester.tavily_client import TavilyClient
from app.services.credit.scoring_engine import ScoringEngine
from app.services.llm import QwenChatService

logger = logging.getLogger(__name__)

_PROMPTS_ROOT = Path(__file__).parent / "prompts"


# =============================================================================
# helpers
# =============================================================================

def _build_harvester() -> PublicWebHarvester:
    tavily = TavilyClient(
        settings.TAVILY_API_KEY,
        settings.TAVILY_API_URL,
        settings.TAVILY_TIMEOUT_SECONDS,
    )
    llm = QwenChatService(settings)
    return PublicWebHarvester(
        tavily,
        llm,
        _PROMPTS_ROOT,
        max_results=settings.TAVILY_MAX_RESULTS_PER_QUERY,
        llm_timeout_seconds=settings.CREDIT_HARVEST_LLM_TIMEOUT_SECONDS,
        llm_retry=settings.CREDIT_HARVEST_LLM_RETRY,
    )


def _parse_date(s: Any) -> date | None:
    if not s or not isinstance(s, str):
        return None
    try:
        return date.fromisoformat(s.strip())
    except ValueError:
        return None


def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _raw(r: HarvestResult, run_id: int) -> dict[str, Any]:
    """落库 raw_data 结构(§4.3)。"""
    return {
        "llm_response": r.raw_llm_response,
        "evidence": r.evidence,
        "confidence": r.confidence,
        "tavily_results": r.tavily_results,
        "harvest_run_id": run_id,
    }


def _aggregate_status(dim_status: dict[str, str]) -> str:
    """4 维度结果汇总成 run.status(§4.6)。"""
    vals = list(dim_status.values())
    if vals and all(v == "failed" for v in vals):
        return HarvestRunStatus.FAILED
    if vals and all(v == "ok" for v in vals):
        return HarvestRunStatus.SUCCEEDED
    return HarvestRunStatus.PARTIAL_SUCCEEDED


async def _find_cache_hit(
    session: AsyncSession, company_id: int
) -> CreditDataHarvestRun | None:
    """24h 内是否有 succeeded / partial_succeeded 的 run(§4.4)。"""
    cutoff = _utcnow() - timedelta(hours=settings.CREDIT_HARVEST_CACHE_TTL_HOURS)
    stmt = (
        select(CreditDataHarvestRun)
        .where(
            CreditDataHarvestRun.company_id == company_id,
            CreditDataHarvestRun.status.in_(
                [HarvestRunStatus.SUCCEEDED, HarvestRunStatus.PARTIAL_SUCCEEDED]
            ),
            CreditDataHarvestRun.started_at >= cutoff,
        )
        .order_by(CreditDataHarvestRun.started_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _audit_trigger(
    session: AsyncSession,
    run: CreditDataHarvestRun,
    triggered_by: str,
    force_refresh: bool,
    operator_user_id: int | None,
) -> None:
    """触发 harvest 时写一条 audit_logs(§4.7:谁触发了 harvest)。"""
    session.add(
        AuditLog(
            trace_id=get_trace_id() or "no-trace",
            user_id=operator_user_id,
            resource_type="credit_harvest_run",
            resource_id=str(run.id),
            action="trigger",
            status="SUCCESS",
            extra={"triggered_by": triggered_by, "force_refresh": force_refresh},
        )
    )


# =============================================================================
# 落快照(维度级)
# =============================================================================

def _persist_basic(
    session: AsyncSession, company_id: int, r: HarvestResult, run_id: int, now: datetime
) -> None:
    if r.status == "failed":
        return  # 失败不落快照
    ex = r.extracted
    session.add(
        CreditCompanyBasicData(
            company_id=company_id,
            established_date=_parse_date(ex.get("established_date")),
            registered_capital=ex.get("registered_capital"),
            business_scope=ex.get("business_scope"),
            legal_representative=ex.get("legal_representative"),
            shareholders=ex.get("shareholders"),
            status_text=ex.get("status_text"),
            address=ex.get("address"),
            website=ex.get("website"),
            data_source=r.data_source,
            fetched_at=now,
            raw_data=_raw(r, run_id),
            harvest_run_id=run_id,
        )
    )


def _persist_finance(
    session: AsyncSession, company_id: int, r: HarvestResult, run_id: int, now: datetime
) -> None:
    if r.status == "failed":
        return
    ex = r.extracted
    session.add(
        CreditCompanyFinanceData(
            company_id=company_id,
            revenue_trend=ex.get("revenue_trend"),
            debt_ratio=_to_decimal(ex.get("debt_ratio")),
            cash_flow_status=ex.get("cash_flow_status"),
            raw_data=_raw(r, run_id),
            data_source=r.data_source,
            fetched_at=now,
            harvest_run_id=run_id,
        )
    )


def _persist_legal(
    session: AsyncSession, company_id: int, r: HarvestResult, run_id: int, now: datetime
) -> None:
    if r.status == "failed":
        return
    ex = r.extracted
    session.add(
        CreditCompanyLegalData(
            company_id=company_id,
            # 这三列 NOT NULL default 0;柬埔寨场景多为 null → 落 0
            litigation_count=ex.get("litigation_count") or 0,
            defaulter_unresolved_count=ex.get("defaulter_unresolved_count") or 0,
            defaulter_resolved_count=ex.get("defaulter_resolved_count") or 0,
            negative_news_level=ex.get("negative_news_level"),
            raw_data=_raw(r, run_id),
            data_source=r.data_source,
            fetched_at=now,
            harvest_run_id=run_id,
        )
    )


_ISO_CERT_MAP = [
    ("has_iso_9001", "ISO 9001", CertType.SYSTEM_GENERAL),
    ("has_iso_14001", "ISO 14001", CertType.SYSTEM_GENERAL),
    ("has_iso_45001", "ISO 45001", CertType.SYSTEM_GENERAL),
    ("has_isc_certification", "ISC Certification", CertType.MANDATORY_COUNTRY),
]


async def _persist_certifications(
    session: AsyncSession,
    company_id: int,
    country_code: str,
    r: HarvestResult,
    run_id: int,
) -> None:
    """证书维度落库。

    证书表是"多行全读"(不像其他三表读最新一条),为避免 mock/旧 harvest 证书与
    本次 public 证书并存污染评分,status=ok/partial 时先清空该 company 现存证书再落新。
    failed / missing 不动旧证书(保留 Δ5 占位)。
    """
    if r.status in ("failed", "missing"):
        return
    await session.execute(
        delete(CreditCompanyCertification).where(
            CreditCompanyCertification.company_id == company_id
        )
    )
    ex = r.extracted
    raw = _raw(r, run_id)
    for field, cert_name, cert_type in _ISO_CERT_MAP:
        if ex.get(field) is True:
            session.add(
                CreditCompanyCertification(
                    company_id=company_id,
                    cert_type=cert_type,
                    cert_name=cert_name,
                    target_country_code=(
                        country_code if cert_type == CertType.MANDATORY_COUNTRY else None
                    ),
                    status=CertStatus.VALID,
                    data_source=r.data_source,
                    raw_data=raw,
                    harvest_run_id=run_id,
                )
            )
    for name in ex.get("other_certifications", []) or []:
        session.add(
            CreditCompanyCertification(
                company_id=company_id,
                cert_type=CertType.INDUSTRY_SPECIFIC,
                cert_name=str(name)[:200],
                status=CertStatus.VALID,
                data_source=r.data_source,
                raw_data=raw,
                harvest_run_id=run_id,
            )
        )


# =============================================================================
# 主流程
# =============================================================================

async def run_harvest_for_company(
    session: AsyncSession,
    company_id: int,
    triggered_by: str,
    operator_user_id: int | None = None,
    force_refresh: bool = False,
    harvester: PublicWebHarvester | None = None,
) -> CreditDataHarvestRun:
    """完整抓取流程。**调用方负责事务提交。**

    harvester 参数仅用于单测注入;生产留 None,内部按 settings 构造。
    """
    company = await session.get(CreditCompany, company_id)
    if company is None:
        raise CompanyNotFoundError(f"company_id={company_id} 不存在")
    now = _utcnow()

    # 1. 缓存检查
    if not force_refresh:
        cached = await _find_cache_hit(session, company_id)
        if cached is not None:
            run = CreditDataHarvestRun(
                company_id=company_id,
                status=HarvestRunStatus.CACHED_HIT,
                triggered_by=triggered_by,
                operator_user_id=operator_user_id,
                started_at=now,
                finished_at=now,
                dimensions_status=dict(cached.dimensions_status or {}),
                cache_source_run_id=cached.id,
                tavily_calls=0,
                llm_calls=0,
            )
            session.add(run)
            await session.flush()
            _audit_trigger(session, run, triggered_by, force_refresh, operator_user_id)
            # 缓存命中:不写新快照、不触发评分(快照不变,评分必然不变)
            return run

    # 2. 写 running run(先拿 id,快照要引用 harvest_run_id)
    run = CreditDataHarvestRun(
        company_id=company_id,
        status=HarvestRunStatus.RUNNING,
        triggered_by=triggered_by,
        operator_user_id=operator_user_id,
        started_at=now,
        dimensions_status={},
        tavily_calls=0,
        llm_calls=0,
    )
    session.add(run)
    await session.flush()
    _audit_trigger(session, run, triggered_by, force_refresh, operator_user_id)

    # 3. 四维度抓取
    h = harvester or _build_harvester()
    name, regno, cc = company.name, company.registration_no, company.country_code
    basic_r = await h.harvest_basic(name, cc, regno)
    finance_r = await h.harvest_finance(name, cc, regno)
    legal_r = await h.harvest_legal(name, cc, regno)
    qual_r = (await h.harvest_qualifications(name, cc, regno))[0]

    dim_status: dict[str, str] = {}
    errors: list[str] = []
    total_tavily = total_llm = 0
    for dim, res in [
        ("basic", basic_r), ("finance", finance_r),
        ("legal", legal_r), ("qualification", qual_r),
    ]:
        dim_status[dim] = res.status
        total_tavily += res.tavily_calls
        total_llm += res.llm_calls
        if res.error:
            errors.append(f"{dim}: {res.error}")

    # 4. 落快照
    _persist_basic(session, company_id, basic_r, run.id, now)
    _persist_finance(session, company_id, finance_r, run.id, now)
    _persist_legal(session, company_id, legal_r, run.id, now)
    await _persist_certifications(session, company_id, cc, qual_r, run.id)
    await session.flush()

    # 5. 更新 run 终态
    run.status = _aggregate_status(dim_status)
    run.finished_at = _utcnow()
    run.dimensions_status = dim_status
    run.tavily_calls = total_tavily
    run.llm_calls = total_llm
    run.error_detail = "; ".join(errors) if errors else None
    await session.flush()

    # 6. 触发评分(即使全 failed 也跑,走 missing 降级路径)
    trigger_type = (
        TriggerType.REAL_TIME_ONBOARD
        if triggered_by == HarvestTriggeredBy.SUPPLIER_REGISTER
        else TriggerType.MANUAL_RECALC
    )
    engine = ScoringEngine(resolve_data_source(cc))
    await engine.compute(
        session=session,
        company_id=company_id,
        trigger_type=trigger_type,
        trigger_detail={"harvest_run_id": run.id, "triggered_by": triggered_by},
        operator_user_id=operator_user_id,
    )
    await session.flush()
    logger.info(
        "harvest done company=%s run=%s status=%s dims=%s",
        company_id, run.id, run.status, dim_status,
    )
    return run


# =============================================================================
# BackgroundTask 入口(各用独立 session,失败只记日志)
# =============================================================================

async def harvest_after_register(supplier_org_id: int) -> None:
    """注册链尾触发抓取(Δ5 占位评分之后)。仅柬埔寨。"""
    try:
        async with AsyncSessionLocal() as db:
            company = (
                await db.execute(
                    select(CreditCompany)
                    .where(CreditCompany.linked_supplier_org_id == supplier_org_id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if company is None:
                logger.warning("harvest skip: supplier_org=%s 无 credit_company", supplier_org_id)
                return
            # 本期仅柬埔寨抓真实数据源;其他国别仍 mock,无需 harvest
            if company.country_code != "KH":
                return
            # 防御:确认 Δ5 占位评分已完成(至少一条 snapshot),否则跳过
            has_snap = (
                await db.execute(
                    select(ScoreSnapshot.id)
                    .where(ScoreSnapshot.company_id == company.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
            if has_snap is None:
                logger.warning("harvest skip: company=%s 尚无占位评分(Δ5 未完成)", company.id)
                return
            await run_harvest_for_company(
                db, company.id, triggered_by=HarvestTriggeredBy.SUPPLIER_REGISTER
            )
            await db.commit()
    except Exception:  # noqa: BLE001 — 异步任务失败不影响注册主流程
        logger.exception("注册触发抓取失败 supplier_org=%s", supplier_org_id)


async def manual_harvest(
    company_id: int, operator_user_id: int, force_refresh: bool = False
) -> None:
    """手动 API 触发抓取。"""
    try:
        async with AsyncSessionLocal() as db:
            await run_harvest_for_company(
                db,
                company_id,
                triggered_by=HarvestTriggeredBy.MANUAL,
                operator_user_id=operator_user_id,
                force_refresh=force_refresh,
            )
            await db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("手动触发抓取失败 company_id=%s", company_id)
