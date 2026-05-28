"""资料卡 · 认证子表(catalog_card_certification)。

A 层字段 8(认证与标准)拆出的独立子表,见预备稿 §3.3。

source 必填(风险底线):
- channel_collected:渠道搜集(初期无供应商时由运营整理,可信度低、仅作背景)
- supplier_uploaded:供应商上传(有供应商后提交,需核实后才可信)

verify_status 默认 unverified,MVP 不挂审批/核实流程,字段位先占住,
后续接入审批流时由 unverified → verified 流转。
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


class CertSource(str, PyEnum):
    CHANNEL_COLLECTED = "channel_collected"
    SUPPLIER_UPLOADED = "supplier_uploaded"


class CertCredibility(str, PyEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CertVerifyStatus(str, PyEnum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


class CatalogCardCertification(Base, TimestampUpdateMixin):
    __tablename__ = "catalog_card_certification"
    __table_args__ = (
        Index(
            "ix_catalog_card_cert_card_order", "card_id", "display_order"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_card.id", name="fk_catalog_card_cert_card"),
        nullable=False,
    )

    cert_name: Mapped[str] = mapped_column(String(100), nullable=False)
    applicable_market: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    credibility: Mapped[str | None] = mapped_column(String(16), nullable=True)
    verify_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CertVerifyStatus.UNVERIFIED.value
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
