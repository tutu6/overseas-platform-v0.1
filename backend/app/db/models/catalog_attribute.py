"""主线一品类属性维度表(catalog_attribute)。

EAV 第二层:定义"某品类有哪些属性维度"。维度名作为数据存放,
而非建独立列,实现表结构跨品类通用。

- attr_type='enum' 的属性,可选值挂在 catalog_attribute_value 表
- attr_type='number' 的属性,取值范围用 min_value/max_value 表达
- is_variant_axis=true 标记核心区分属性(铝卷=牌号),驱动资料卡
  内容分组、选型引导、显示顺序;对应业界 PIM variant axis 概念
"""
from __future__ import annotations

from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class AttrType(str, PyEnum):
    ENUM = "enum"
    NUMBER = "number"


class CatalogAttribute(Base, TimestampUpdateMixin):
    __tablename__ = "catalog_attribute"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "attr_code", name="uq_catalog_attribute_category_code"
        ),
        Index(
            "ix_catalog_attribute_category_order", "category_id", "display_order"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_category.id", name="fk_catalog_attribute_category"),
        nullable=False,
    )
    attr_code: Mapped[str] = mapped_column(String(32), nullable=False)
    attr_name: Mapped[str] = mapped_column(String(64), nullable=False)
    attr_type: Mapped[str] = mapped_column(String(16), nullable=False)
    attr_unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    min_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    decimal_places: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    is_filterable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_variant_axis: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
