"""信用评估评分引擎(信用评估 §3.2)。

主入口:`ScoringEngine.compute(session, company_id, trigger_type, trigger_detail)`
输出:写入 score_snapshot + score_detail(每快照 12 条)+ score_audit_log(若分数变化)
       + 平台 audit_logs(若分数变化)。返回新快照 ORM。

事务:6-8 步在单事务内提交(原子)。
AI 评价生成由调用方在事务提交后单独触发(seed 跳过、API 同步生成)。
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import _utcnow
from app.db.models import (
    AuditLog,
    CreditCompany,
    Grade,
    ScoreAuditLog,
    ScoreDetail,
    ScoreDimension,
    ScoreRule,
    ScoreSnapshot,
    ScoreSubitem,
    TriggerType,
)
from app.services.credit.data_source.base import DataSource
from app.services.credit.errors import CompanyNotFoundError
from app.services.credit.evaluators import EVALUATORS
from app.services.credit.types import (
    DimensionResult,
    EvaluationInput,
    ScoringResult,
    SubitemResult,
)

logger = logging.getLogger(__name__)


GRADE_THRESHOLDS = [
    (80, Grade.A),
    (60, Grade.B),
    (40, Grade.C),
    (0, Grade.D),
]


def _grade_of(total: int) -> str:
    for threshold, g in GRADE_THRESHOLDS:
        if total >= threshold:
            return g
    return Grade.D


class ScoringEngine:
    """评分引擎。

    DI:DataSource 通过构造注入,便于单测换 mock 数据源。
    """

    def __init__(self, data_source: DataSource) -> None:
        self._data_source = data_source

    # =========================================================================
    # 主入口
    # =========================================================================
    async def compute(
        self,
        session: AsyncSession,
        company_id: int,
        trigger_type: str,
        trigger_detail: dict[str, Any] | None = None,
        operator_user_id: int | None = None,
    ) -> ScoreSnapshot:
        """完整评分流程。**调用方负责事务提交。**

        本方法在传入 session 上 flush 但不 commit,允许 API 层包一个大事务。
        AI 评价生成由调用方在 commit 后另起调用。
        """
        # ---- 1. 加载公司 ----
        company = await session.get(CreditCompany, company_id)
        if company is None:
            raise CompanyNotFoundError(f"company_id={company_id} 不存在")

        # ---- 2. 加载 active 规则集 ----
        dims, subitems, rules_by_subitem = await self._load_rules(session)
        if not dims:
            raise RuntimeError("score_dimension 未配置;先执行 seed_credit_module()")

        rule_version = max(d.version for d in dims)  # 各维度 version 应该一致

        # ---- 3. 拉数据 ----
        basic = await self._data_source.fetch_basic_data(session, company_id)
        finance = await self._data_source.fetch_finance_data(session, company_id)
        legal = await self._data_source.fetch_legal_data(session, company_id)
        certs = await self._data_source.fetch_certifications(session, company_id)

        ctx = EvaluationInput(
            company_id=company_id,
            country_code=company.country_code,
            basic=basic,
            finance=finance,
            legal=legal,
            certifications=certs,
            today=date.today(),
        )
        # 给 evaluator 用的 plain dict(扁平,JSON 序列化友好)
        ctx_dict = self._to_eval_dict(ctx)

        # ---- 4. 求值各 subitem ----
        dim_results: list[DimensionResult] = []
        for dim in sorted(dims, key=lambda d: d.display_order):
            dim_subs = [s for s in subitems if s.dimension_id == dim.id]
            dim_subs.sort(key=lambda s: s.display_order)
            sub_results: list[SubitemResult] = []
            for sub in dim_subs:
                rules = sorted(
                    rules_by_subitem.get(sub.id, []), key=lambda r: r.priority
                )
                sub_result = self._evaluate_subitem(sub, rules, ctx_dict)
                sub_results.append(sub_result)
            dim_score = sum(r.score for r in sub_results)
            dim_results.append(
                DimensionResult(
                    dimension_code=dim.code,
                    score=dim_score,
                    max_score=dim.max_score,
                    subitems=sub_results,
                )
            )

        total = sum(d.score for d in dim_results)
        grade = _grade_of(total)

        # ---- 5. 包装中间结果 ----
        # 维度顺序按 display_order(1-4 严格对齐 PRD)
        d_scores = {d.dimension_code: d.score for d in dim_results}
        result = ScoringResult(
            company_id=company_id,
            total_score=total,
            grade=grade,
            dimensions=dim_results,
            rule_version=rule_version,
            basic_data_id=getattr(basic, "id", None) if not basic.is_missing else None,
            finance_data_id=(
                getattr(finance, "id", None) if not finance.is_missing else None
            ),
            legal_data_id=(
                getattr(legal, "id", None) if not legal.is_missing else None
            ),
        )

        # ---- 6-8. 写库(同事务)----
        snapshot = await self._persist(
            session=session,
            company=company,
            result=result,
            dims=dims,
            subitems=subitems,
            ctx_dict=ctx_dict,
            trigger_type=trigger_type,
            trigger_detail=trigger_detail,
            operator_user_id=operator_user_id,
            d_scores=d_scores,
        )

        return snapshot

    # =========================================================================
    # 内部
    # =========================================================================
    async def _load_rules(
        self, session: AsyncSession
    ) -> tuple[list[ScoreDimension], list[ScoreSubitem], dict[int, list[ScoreRule]]]:
        dims_q = select(ScoreDimension).where(ScoreDimension.is_active.is_(True))
        subs_q = select(ScoreSubitem).where(ScoreSubitem.is_active.is_(True))
        rules_q = select(ScoreRule).where(ScoreRule.is_active.is_(True))
        dims = list((await session.execute(dims_q)).scalars().all())
        subs = list((await session.execute(subs_q)).scalars().all())
        rules = list((await session.execute(rules_q)).scalars().all())
        rules_by_sub: dict[int, list[ScoreRule]] = {}
        for r in rules:
            rules_by_sub.setdefault(r.subitem_id, []).append(r)
        return dims, subs, rules_by_sub

    @staticmethod
    def _to_eval_dict(ctx: EvaluationInput) -> dict[str, Any]:
        # `mode="json"` 把 date/datetime/Decimal 都转成 JSON 友好类型;
        # `today` 也走 isoformat,evaluators 内 _today() 会 parse 回 date。
        return {
            "company_id": ctx.company_id,
            "country_code": ctx.country_code,
            "basic": ctx.basic.model_dump(mode="json"),
            "finance": ctx.finance.model_dump(mode="json"),
            "legal": ctx.legal.model_dump(mode="json"),
            "certifications": [c.model_dump(mode="json") for c in ctx.certifications],
            "today": ctx.today.isoformat(),
        }

    @staticmethod
    def _evaluate_subitem(
        sub: ScoreSubitem,
        rules: list[ScoreRule],
        ctx_dict: dict[str, Any],
    ) -> SubitemResult:
        """对单 subitem 求值:按 priority 升序遍历,首条命中即停。"""
        for r in rules:
            fn = EVALUATORS.get(r.evaluator_key)
            if fn is None:
                # 孤儿规则:启动时已 warn,这里直接跳过
                logger.warning(
                    "evaluator '%s' 不存在,跳过 rule %s", r.evaluator_key, r.code
                )
                continue
            try:
                hit = fn(ctx_dict)
            except Exception:  # noqa: BLE001
                logger.exception("evaluator '%s' 抛错,视为未命中", r.evaluator_key)
                hit = False
            if hit:
                return SubitemResult(
                    subitem_code=sub.code,
                    score=r.score,
                    hit_rule_code=r.code,
                    hit_rule_description=r.description,
                    is_default_score=False,
                )
        # 全部未命中 → 默认分
        return SubitemResult(
            subitem_code=sub.code,
            score=sub.default_score,
            hit_rule_code=None,
            hit_rule_description=None,
            is_default_score=True,
        )

    async def _persist(
        self,
        session: AsyncSession,
        company: CreditCompany,
        result: ScoringResult,
        dims: list[ScoreDimension],
        subitems: list[ScoreSubitem],
        ctx_dict: dict[str, Any],
        trigger_type: str,
        trigger_detail: dict[str, Any] | None,
        operator_user_id: int | None,
        d_scores: dict[str, int],
    ) -> ScoreSnapshot:
        """写 snapshot + detail + audit。"""
        # 旧快照 is_current 切 false
        prev_q = select(ScoreSnapshot).where(
            ScoreSnapshot.company_id == company.id,
            ScoreSnapshot.is_current.is_(True),
        )
        prev = (await session.execute(prev_q)).scalar_one_or_none()
        if prev is not None:
            await session.execute(
                update(ScoreSnapshot)
                .where(ScoreSnapshot.id == prev.id)
                .values(is_current=False)
            )

        # 维度 1-4 按 display_order 映射(PRD 顺序固定)
        dim_by_order = {d.display_order: d.code for d in sorted(dims, key=lambda d: d.display_order)}
        # PRD: 维度1 基础工商 / 维度2 资质 / 维度3 财务 / 维度4 司法
        d1 = d_scores.get(dim_by_order.get(1, ""), 0)
        d2 = d_scores.get(dim_by_order.get(2, ""), 0)
        d3 = d_scores.get(dim_by_order.get(3, ""), 0)
        d4 = d_scores.get(dim_by_order.get(4, ""), 0)

        now = _utcnow()
        snapshot = ScoreSnapshot(
            company_id=company.id,
            total_score=result.total_score,
            grade=result.grade,
            dimension_1_score=d1,
            dimension_2_score=d2,
            dimension_3_score=d3,
            dimension_4_score=d4,
            rule_version=result.rule_version,
            trigger_type=trigger_type,
            trigger_detail=trigger_detail,
            basic_data_id=result.basic_data_id,
            finance_data_id=result.finance_data_id,
            legal_data_id=result.legal_data_id,
            is_current=True,
            calculated_at=now,
        )
        session.add(snapshot)
        await session.flush()  # 拿到 snapshot.id

        # 写 12 条 score_detail
        sub_by_id = {s.id: s for s in subitems}
        dim_by_id = {d.id: d for d in dims}
        for dim_result in result.dimensions:
            dim = next(d for d in dims if d.code == dim_result.dimension_code)
            for sub_r in dim_result.subitems:
                sub = next(s for s in subitems if s.code == sub_r.subitem_code)
                session.add(
                    ScoreDetail(
                        snapshot_id=snapshot.id,
                        company_id=company.id,
                        dimension_code=dim.code,
                        dimension_name=dim.name,
                        subitem_code=sub.code,
                        subitem_name=sub.name,
                        hit_rule_code=sub_r.hit_rule_code,
                        hit_rule_description=sub_r.hit_rule_description,
                        score=sub_r.score,
                        max_score=sub.max_score,
                        is_default_score=sub_r.is_default_score,
                        evaluation_context=ctx_dict,
                    )
                )

        # 评分变动审计
        if prev is None or prev.total_score != snapshot.total_score or prev.grade != snapshot.grade:
            changed_items: list[dict[str, Any]] = []
            if prev is not None:
                # 简化:目前仅记总分 / 等级变化,子项差异留 TODO(T-5 趋势分析时实现)
                # TODO(T-5): 对比上一快照的 score_detail 计算子项级差异
                changed_items.append(
                    {
                        "type": "summary",
                        "previous_total_score": prev.total_score,
                        "current_total_score": snapshot.total_score,
                        "previous_grade": prev.grade,
                        "current_grade": snapshot.grade,
                    }
                )
            session.add(
                ScoreAuditLog(
                    company_id=company.id,
                    previous_snapshot_id=prev.id if prev else None,
                    current_snapshot_id=snapshot.id,
                    previous_total_score=prev.total_score if prev else None,
                    current_total_score=snapshot.total_score,
                    score_delta=snapshot.total_score - (prev.total_score if prev else 0),
                    previous_grade=prev.grade if prev else None,
                    current_grade=snapshot.grade,
                    grade_changed=(prev is None) or (prev.grade != snapshot.grade),
                    changed_subitems=changed_items,
                    trigger_type=trigger_type,
                )
            )
            # 平台 audit_logs(谁做了什么);trace_id 从 contextvar 取
            if operator_user_id is not None:
                from app.audit.context import get_trace_id  # 内部导入避免循环引用

                session.add(
                    AuditLog(
                        trace_id=get_trace_id() or "no-trace",
                        user_id=operator_user_id,
                        resource_type="credit_company",
                        resource_id=str(company.id),
                        action="CREDIT_RECOMPUTE",
                        status="SUCCESS",
                        extra={
                            "trigger_type": trigger_type,
                            "previous_total_score": prev.total_score if prev else None,
                            "current_total_score": snapshot.total_score,
                            "current_grade": snapshot.grade,
                        },
                    )
                )

        await session.flush()
        return snapshot
