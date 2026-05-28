"""主线一属性枚举值表(catalog_attribute_value)。

EAV 第三层:挂枚举型属性的可选取值(数值型不进此表,用 min/max 表达)。
新增牌号 = 加 1 行,结构不变。
"""
from __future__ import annotations

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CatalogAttributeValue(Base, TimestampUpdateMixin):
    __tablename__ = "catalog_attribute_value"
    __table_args__ = (
        UniqueConstraint(
            "attr_id", "value", name="uq_catalog_attribute_value_attr_value"
        ),
        Index(
            "ix_catalog_attribute_value_attr_order", "attr_id", "value_order"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    attr_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "catalog_attribute.id", name="fk_catalog_attribute_value_attr"
        ),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    value_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
