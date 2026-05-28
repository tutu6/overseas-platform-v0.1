"""资料卡 · 厂商子表(catalog_card_supplier)。

A 层字段 5(全球主流厂商)拆出的独立子表,见预备稿 §3.3。
存两类厂商的展示信息:
- 已入驻供应商:linked_supplier_id 指向 supplier_organizations 主体
- 渠道搜集的未入驻厂商:linked_supplier_id 为 NULL,仅作信息条目

country_code + registration_no 用于未入驻厂商被邀请入驻后,
通过(country_code, registration_no)复合键自动关联到正式供应商主体
(与供应商注册防重同一把钥匙)。
"""
from __future__ import annotations

from enum import Enum as PyEnum

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampUpdateMixin


class CardSupplierReviewStatus(str, PyEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class CatalogCardSupplier(Base, TimestampUpdateMixin):
    __tablename__ = "catalog_card_supplier"
    __table_args__ = (
        Index(
            "ix_catalog_card_supplier_card_order", "card_id", "display_order"
        ),
        Index(
            "ix_catalog_card_supplier_country_regno",
            "country_code",
            "registration_no",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_card.id", name="fk_catalog_card_supplier_card"),
        nullable=False,
    )

    supplier_name: Mapped[str] = mapped_column(String(200), nullable=False)
    headquarter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scale: Mapped[str | None] = mapped_column(String(200), nullable=True)
    main_products: Mapped[str | None] = mapped_column(Text, nullable=True)
    overseas_track_record: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 厂商主体自动关联机制
    linked_supplier_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "supplier_organizations.id",
            name="fk_catalog_card_supplier_linked",
        ),
        nullable=True,
    )
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)

    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CardSupplierReviewStatus.DRAFT.value
    )
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
