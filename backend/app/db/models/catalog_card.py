"""主线一品类资料卡主表(catalog_card)。

A 层资料卡内容承载。一个品类一张卡(category_id 唯一)。
存储归属遵循预备稿 §3.1:
- 单值文本型字段(1/9):text 列
- 多项展示型字段(4 产地、7 成本、10 风险):JSONB
- 字段 2/3(核心参数 / 规格场景):本期静态文本,Step 3 读接口不做 B 层动态拼接
- 字段 5(厂商)、字段 8(认证)拆独立子表
- 字段 6(价格):本期不入主表,留待价格子系统独立议题

字段级可信度色标(🟢🟡🟠🔴)落 confidence_marks JSONB,代表四家 AI
共识度,**非正确性背书**。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CardReviewStatus(str, PyEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PUBLISHED = "published"


class CatalogCard(Base, TimestampUpdateMixin):
    __tablename__ = "catalog_card"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_category.id", name="fk_catalog_card_category"),
        nullable=False,
        unique=True,
    )

    # A 层字段(按预备稿 §3.2 字段编号与主线一通用字段表 v0.3 对应)
    field_1_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_2_tech_params: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_3_spec_scene: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_4_origin: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    field_7_cost: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    field_9_logistics: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_10_risk: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # 卡级元数据
    confidence_marks: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="v0.1")
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CardReviewStatus.DRAFT.value
    )
