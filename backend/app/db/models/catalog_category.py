"""主线一品类表(catalog_category)。

分类树根节点,1 级。每个品类挂一张资料卡(catalog_card)与若干
属性维度(catalog_attribute)。code 是业务编码,永久不变,前端
路由参数将引用它(/catalog/aluminum-coil)。
"""
from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import Index, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CategoryStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class CatalogCategory(Base, TimestampUpdateMixin):
    __tablename__ = "catalog_category"
    __table_args__ = (
        Index("ix_catalog_category_status_order", "status", "display_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name_zh: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(128), nullable=True)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CategoryStatus.ACTIVE.value
    )
