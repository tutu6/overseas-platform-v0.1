"""信用评估路由 /api/v1/credit/*(对齐技术方案 §四)。

9 个端点:
- 搜索 / 详情
- 触发重算(单家 / 全平台)
- 搜索历史(查 / 删)
- AI 会话 + 流式消息

权限:
- credit:read         全员
- credit:recompute    OPERATOR / ADMIN
"""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import CurrentUser
from app.core.exceptions import BusinessError, success
from app.db.base import _utcnow
from app.db.models import (
    CreditAiConversation,
    CreditAiMessage,
    CreditCompany,
    CreditSearchHistory,
    MessageRole,
    ScoreDetail,
    ScoreDimension,
    ScoreSnapshot,
    TriggerType,
)
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.db.session import get_db
from app.schemas.credit import (
    AiConversationCreateIn,
    AiConversationOut,
    AiMessageOut,
    AiMessageSendIn,
    BasicDataOut,
    CertificationOut,
    CompanyDetailOut,
    CompanyListItem,
    DimensionOut,
    FinanceDataOut,
    LegalDataOut,
    ScoreDetailOut,
    SearchHistoryItem,
    SnapshotOut,
    TriggerDetail,
)
from app.services.credit.ai_summary_generator import AISummaryGenerator
from app.services.credit.data_source.registry import resolve_data_source
from app.services.credit.scoring_engine import ScoringEngine
from app.services.llm import LLMUnavailableError, QwenChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/credit", tags=["credit"])

SEARCH_RESULT_LIMIT = 20
SEARCH_HISTORY_LIMIT = 5


def _llm_service() -> QwenChatService:
    """每次请求实例化一个轻量 LLM 客户端;httpx connection pool 内置复用。"""
    return QwenChatService(settings)


# =============================================================================
# 1. 搜索候选企业
# =============================================================================

@router.get("/companies/search", summary="搜索候选企业(国别 + 关键词)")
async def search_companies(
    country: str = Query("", description="国别 ISO-2 码;留空表示全部"),
    q: str = Query("", description="企业名/英文名/注册号关键词"),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(CreditCompany)
    if country:
        stmt = stmt.where(CreditCompany.country_code == country.upper())
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CreditCompany.name.ilike(like),
                CreditCompany.legal_name_en.ilike(like),
                CreditCompany.registration_no.ilike(like),
            )
        )
    stmt = stmt.order_by(CreditCompany.created_at.desc()).limit(SEARCH_RESULT_LIMIT)
    companies = list((await db.execute(stmt)).scalars().all())

    # 批量取最新 is_current 快照
    snap_map: dict[int, ScoreSnapshot] = {}
    if companies:
        ids = [c.id for c in companies]
        snap_stmt = select(ScoreSnapshot).where(
            ScoreSnapshot.company_id.in_(ids),
            ScoreSnapshot.is_current.is_(True),
        )
        for s in (await db.execute(snap_stmt)).scalars().all():
            snap_map[s.company_id] = s

    items = []
    for c in companies:
        snap = snap_map.get(c.id)
        items.append(
            CompanyListItem(
                id=c.id, name=c.name, legal_name_en=c.legal_name_en,
                country_code=c.country_code, registration_no=c.registration_no,
                total_score=snap.total_score if snap else None,
                grade=snap.grade if snap else None,
            ).model_dump(mode="json")
        )
    _ = current  # 仅鉴权,未使用 user_id
    return success(items)


# =============================================================================
# 2. 企业详情(首访自动生成 ai_summary)
# =============================================================================

@router.get("/companies/{company_id}", summary="企业详情")
async def get_company_detail(
    company_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")

    # 写搜索历史(同 company 去重:删旧+写新)
    await db.execute(
        delete(CreditSearchHistory).where(
            CreditSearchHistory.user_id == current.id,
            CreditSearchHistory.company_id == company_id,
        )
    )
    db.add(
        CreditSearchHistory(
            user_id=current.id,
            company_id=company_id,
            searched_at=_utcnow(),
        )
    )
    await db.commit()

    # 拿当前快照
    snap_stmt = select(ScoreSnapshot).where(
        ScoreSnapshot.company_id == company_id,
        ScoreSnapshot.is_current.is_(True),
    )
    snapshot = (await db.execute(snap_stmt)).scalar_one_or_none()

    # 没快照说明 seed 阶段评分还未触发(异常路径)→ 触发一次
    if snapshot is None:
        engine = ScoringEngine(resolve_data_source(company.country_code))
        snapshot = await engine.compute(
            session=db,
            company_id=company_id,
            trigger_type=TriggerType.INITIAL,
            trigger_detail={"source": "detail_view_fallback"},
            operator_user_id=current.id,
        )
        await db.commit()

    # ai_summary 为空时同步生成(工单 Step 11)
    if snapshot.ai_summary is None:
        try:
            generator = AISummaryGenerator(_llm_service())
            await generator.generate_for_snapshot(db, snapshot.id)
            await db.commit()
            await db.refresh(snapshot)
        except LLMUnavailableError as exc:
            # 不阻断详情页渲染;前端会显示"AI 评价暂时不可用"
            logger.warning("AI summary 生成失败 company_id=%s: %s", company_id, exc)
        except Exception:  # noqa: BLE001
            logger.exception("AI summary 生成抛错 company_id=%s", company_id)

    # 12 条 score_detail
    detail_stmt = (
        select(ScoreDetail)
        .where(ScoreDetail.snapshot_id == snapshot.id)
        .order_by(ScoreDetail.dimension_code, ScoreDetail.subitem_code)
    )
    details_rows = list((await db.execute(detail_stmt)).scalars().all())

    # 维度元信息 + 当前分
    dims_stmt = select(ScoreDimension).order_by(ScoreDimension.display_order)
    dims_rows = list((await db.execute(dims_stmt)).scalars().all())
    dim_outs = [
        DimensionOut(
            code=d.code, name=d.name, max_score=d.max_score,
            score=getattr(snapshot, f"dimension_{d.display_order}_score"),
        )
        for d in dims_rows
    ]

    # 工商 / 财务 / 司法 最新数据(从 snapshot 引用的 ID 取;若 ID 为空则当前查最新)
    basic_out: BasicDataOut | None = None
    finance_out: FinanceDataOut | None = None
    legal_out: LegalDataOut | None = None
    if snapshot.basic_data_id is not None:
        from app.db.models import CreditCompanyBasicData
        basic_row = await db.get(CreditCompanyBasicData, snapshot.basic_data_id)
        basic_out = BasicDataOut.model_validate(basic_row) if basic_row else None
    if snapshot.finance_data_id is not None:
        from app.db.models import CreditCompanyFinanceData
        finance_row = await db.get(CreditCompanyFinanceData, snapshot.finance_data_id)
        finance_out = FinanceDataOut.model_validate(finance_row) if finance_row else None
    if snapshot.legal_data_id is not None:
        from app.db.models import CreditCompanyLegalData
        legal_row = await db.get(CreditCompanyLegalData, snapshot.legal_data_id)
        legal_out = LegalDataOut.model_validate(legal_row) if legal_row else None

    # 证书(不分快照,全部当前)
    from app.db.models import CreditCompanyCertification
    cert_stmt = (
        select(CreditCompanyCertification)
        .where(CreditCompanyCertification.company_id == company_id)
        .order_by(CreditCompanyCertification.cert_type, CreditCompanyCertification.id)
    )
    cert_rows = list((await db.execute(cert_stmt)).scalars().all())

    payload = CompanyDetailOut(
        id=company.id,
        name=company.name,
        legal_name_en=company.legal_name_en,
        country_code=company.country_code,
        registration_no=company.registration_no,
        snapshot=SnapshotOut.model_validate(snapshot),
        dimensions=dim_outs,
        details=[ScoreDetailOut.model_validate(d) for d in details_rows],
        basic=basic_out,
        finance=finance_out,
        legal=legal_out,
        certifications=[CertificationOut.model_validate(c) for c in cert_rows],
    )
    return success(payload.model_dump(mode="json"))


# =============================================================================
# 3. 单家重算
# =============================================================================

@router.post("/companies/{company_id}/recompute", summary="单家重算")
async def recompute_company(
    company_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_RECOMPUTE)),
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(CreditCompany, company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")

    engine = ScoringEngine(resolve_data_source(company.country_code))
    snapshot = await engine.compute(
        session=db,
        company_id=company_id,
        trigger_type=TriggerType.MANUAL_RECALC,
        trigger_detail=TriggerDetail(
            actor_user_id=current.id,
            actor_email=current.email,
            source="api",
        ).model_dump(),
        operator_user_id=current.id,
    )
    await db.commit()

    # AI summary 同步生成
    try:
        generator = AISummaryGenerator(_llm_service())
        await generator.generate_for_snapshot(db, snapshot.id)
        await db.commit()
        await db.refresh(snapshot)
    except LLMUnavailableError as exc:
        logger.warning("AI summary 生成失败 company_id=%s: %s", company_id, exc)
    except Exception:  # noqa: BLE001
        logger.exception("AI summary 生成抛错 company_id=%s", company_id)

    return success(SnapshotOut.model_validate(snapshot).model_dump(mode="json"))


# =============================================================================
# 4. 全平台重算(占位接口,T-1 / T+1 跑批前供 ADMIN 手动触发)
# =============================================================================

@router.post("/recompute-all", summary="全平台重算(占位)")
async def recompute_all(
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_RECOMPUTE)),
    db: AsyncSession = Depends(get_db),
):
    """遍历所有 CreditCompany,逐家重算。本期无并发限流。

    TODO(T-1): 接入 T+1 调度后改异步队列。
    """
    rows = list((await db.execute(select(CreditCompany))).scalars().all())
    recomputed = []
    for c in rows:
        engine = ScoringEngine(resolve_data_source(c.country_code))
        snapshot = await engine.compute(
            session=db,
            company_id=c.id,
            trigger_type=TriggerType.MANUAL_RECALC,
            trigger_detail=TriggerDetail(
                actor_user_id=current.id,
                actor_email=current.email,
                source="api_recompute_all",
            ).model_dump(),
            operator_user_id=current.id,
        )
        await db.commit()
        recomputed.append({"company_id": c.id, "total_score": snapshot.total_score, "grade": snapshot.grade})

    return success({"count": len(recomputed), "items": recomputed})


# =============================================================================
# 5. 搜索历史
# =============================================================================

@router.get("/search-history", summary="当前用户最近 5 条搜索历史")
async def list_search_history(
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    # 同 company 去重:每个 company 只保留 max(searched_at) 那一条
    sub = (
        select(
            CreditSearchHistory.company_id,
            func.max(CreditSearchHistory.searched_at).label("max_at"),
        )
        .where(CreditSearchHistory.user_id == current.id)
        .group_by(CreditSearchHistory.company_id)
        .subquery()
    )
    stmt = (
        select(CreditSearchHistory, CreditCompany)
        .join(
            sub,
            (CreditSearchHistory.company_id == sub.c.company_id)
            & (CreditSearchHistory.searched_at == sub.c.max_at),
        )
        .join(CreditCompany, CreditCompany.id == CreditSearchHistory.company_id)
        .where(CreditSearchHistory.user_id == current.id)
        .order_by(CreditSearchHistory.searched_at.desc())
        .limit(SEARCH_HISTORY_LIMIT)
    )

    # 取每条 company 的当前 grade
    rows = list((await db.execute(stmt)).all())
    if not rows:
        return success([])
    company_ids = [c.id for _, c in rows]
    snap_map: dict[int, ScoreSnapshot] = {}
    snap_stmt = select(ScoreSnapshot).where(
        ScoreSnapshot.company_id.in_(company_ids),
        ScoreSnapshot.is_current.is_(True),
    )
    for s in (await db.execute(snap_stmt)).scalars().all():
        snap_map[s.company_id] = s

    items = [
        SearchHistoryItem(
            id=h.id, company_id=c.id, company_name=c.name, country_code=c.country_code,
            grade=(snap_map.get(c.id).grade if snap_map.get(c.id) else None),
            searched_at=h.searched_at,
        ).model_dump(mode="json")
        for h, c in rows
    ]
    return success(items)


@router.delete("/search-history/{history_id}", summary="删除一条搜索历史")
async def delete_search_history(
    history_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(CreditSearchHistory, history_id)
    if row is None or row.user_id != current.id:
        raise BusinessError(http_status=404, biz_code=40404, message="历史记录不存在")
    await db.delete(row)
    await db.commit()
    return success({"deleted": history_id})


# =============================================================================
# 6-8. AI 会话
# =============================================================================

@router.post("/ai/conversations", summary="创建 AI 会话")
async def create_ai_conversation(
    body: AiConversationCreateIn,
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    company = await db.get(CreditCompany, body.company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")
    conv = CreditAiConversation(
        user_id=current.id,
        company_id=body.company_id,
        started_at=_utcnow(),
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return success(
        AiConversationOut.model_validate(conv).model_dump(mode="json")
    )


@router.get("/ai/conversations/{conv_id}", summary="获取会话历史")
async def get_ai_conversation(
    conv_id: int = Path(..., ge=1),
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    conv = await db.get(CreditAiConversation, conv_id)
    if conv is None or conv.user_id != current.id:
        raise BusinessError(http_status=404, biz_code=40404, message="会话不存在")
    msg_stmt = (
        select(CreditAiMessage)
        .where(CreditAiMessage.conversation_id == conv_id)
        .order_by(CreditAiMessage.sequence)
    )
    msgs = list((await db.execute(msg_stmt)).scalars().all())
    out = AiConversationOut.model_validate(conv)
    out.messages = [AiMessageOut.model_validate(m) for m in msgs]
    return success(out.model_dump(mode="json"))


@router.post(
    "/ai/conversations/{conv_id}/messages",
    summary="发送对话消息(SSE 流式响应)",
)
async def send_ai_message(
    conv_id: int,
    body: AiMessageSendIn,
    current: CurrentUser = Depends(require_permission(Permissions.CREDIT_READ)),
    db: AsyncSession = Depends(get_db),
):
    """流式返回 LLM 输出。响应 Content-Type=text/event-stream,逐 chunk 推 data 字段。

    流完整后将 assistant 完整内容落库一条 message。
    """
    conv = await db.get(CreditAiConversation, conv_id)
    if conv is None or conv.user_id != current.id:
        raise BusinessError(http_status=404, biz_code=40404, message="会话不存在")

    company = await db.get(CreditCompany, conv.company_id)
    if company is None:
        raise BusinessError(http_status=404, biz_code=40404, message="企业不存在")

    # 取当前快照(用于在 system prompt 中提供企业上下文)
    snap = (
        await db.execute(
            select(ScoreSnapshot).where(
                ScoreSnapshot.company_id == conv.company_id,
                ScoreSnapshot.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()

    # 历史消息按 sequence
    msgs_stmt = (
        select(CreditAiMessage)
        .where(CreditAiMessage.conversation_id == conv_id)
        .order_by(CreditAiMessage.sequence)
    )
    history = list((await db.execute(msgs_stmt)).scalars().all())

    # 写本轮 user 消息
    next_seq = (history[-1].sequence + 1) if history else 1
    user_msg = CreditAiMessage(
        conversation_id=conv_id,
        role=MessageRole.USER,
        content=body.content,
        sequence=next_seq,
    )
    db.add(user_msg)
    await db.commit()

    # 构造 LLM messages(system + history + this user message)
    system_prompt = (
        f"你是海外工程供应链领域的企业风控分析师助手。"
        f"用户正在咨询的企业是 '{company.name}'(国别 {company.country_code})。"
    )
    if snap is not None:
        system_prompt += (
            f" 该企业当前综合评分 {snap.total_score} 分 ({snap.grade} 级)。"
            f" 已缓存评价摘要:{snap.ai_summary or '尚未生成'}。"
        )
    llm_messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in history:
        llm_messages.append({"role": m.role, "content": m.content})
    llm_messages.append({"role": MessageRole.USER, "content": body.content})

    llm = _llm_service()

    async def event_stream() -> AsyncIterator[bytes]:
        """SSE 帧格式:`data: <text>\\n\\n`。流完一行 `data: [DONE]\\n\\n`。"""
        collected: list[str] = []
        try:
            async for chunk in llm.stream_chat(llm_messages):
                collected.append(chunk)
                # 转义换行,避免 SSE data 多行混淆
                safe = chunk.replace("\n", "\\n")
                yield f"data: {safe}\n\n".encode("utf-8")
        except LLMUnavailableError as exc:
            err = json.dumps({"error": str(exc)}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n".encode("utf-8")
            return
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE 流式中断")
            err = json.dumps({"error": "internal_error"}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n".encode("utf-8")
            return

        # 流完整 → 落库 assistant 消息(注意:这里启用一个新 session,旧 db 会话已 close)
        full_content = "".join(collected).strip()
        if full_content:
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as new_db:
                new_db.add(
                    CreditAiMessage(
                        conversation_id=conv_id,
                        role=MessageRole.ASSISTANT,
                        content=full_content,
                        sequence=next_seq + 1,
                    )
                )
                await new_db.commit()

        yield b"data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关闭 nginx/反代缓冲
        },
    )
