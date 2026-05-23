"""评分快照(信用评估 §二)。

每次评分写一条新快照,旧快照 is_current 切为 false。部分唯一索引保证
每个 company 同时只能有一条 is_current=true 的快照。

trigger_type 枚举:
- INITIAL              首次评分(seed/入库时)
- MANUAL_RECALC        人工触发重算
- T_PLUS_1_BATCH       T+1 跑批(TODO T-1)
- REAL_TIME_ONBOARD    实时入库 + 算分(TODO T-7)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Grade:
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    ALL = (A, B, C, D)


class TriggerType:
    INITIAL = "INITIAL"
    MANUAL_RECALC = "MANUAL_RECALC"
    T_PLUS_1_BATCH = "T_PLUS_1_BATCH"
    REAL_TIME_ONBOARD = "REAL_TIME_ONBOARD"


class ScoreSnapshot(Base, TimestampMixin):
    __tablename__ = "score_snapshot"
    __table_args__ = (
        # 部分唯一索引:每个 company 同时只能有一条 is_current=true
        Index(
            "uq_score_snapshot_current",
            "company_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
        Index(
            "ix_score_snapshot_company_calculated",
            "company_id",
            text("calculated_at DESC"),
        ),
        Index("ix_score_snapshot_grade_current", "grade", "is_current"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("credit_company.id", name="fk_score_snapshot_company"),
        nullable=False,
    )
    total_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    grade: Mapped[str] = mapped_column(String(1), nullable=False)
    dimension_1_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dimension_2_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dimension_3_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dimension_4_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    basic_data_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "credit_company_basic_data.id", name="fk_score_snapshot_basic_data"
        ),
        nullable=True,
    )
    finance_data_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "credit_company_finance_data.id", name="fk_score_snapshot_finance_data"
        ),
        nullable=True,
    )
    legal_data_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "credit_company_legal_data.id", name="fk_score_snapshot_legal_data"
        ),
        nullable=True,
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_summary_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
