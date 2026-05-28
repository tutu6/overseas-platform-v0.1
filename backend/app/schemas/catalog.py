"""主线一品类资料卡读接口 Pydantic schemas(工单 17 · Step 3)。

读接口本期**原样返回存储内容**,字段 2/3 不做 B 层动态拼接;
B 层属性维度作为独立字段一并返回,前端/调用方按需使用。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class AttributeValueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    value: str
    value_order: int


class AttributeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    attr_code: str
    attr_name: str
    attr_type: str
    attr_unit: str | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    decimal_places: int | None = None
    is_filterable: bool
    is_variant_axis: bool
    display_order: int
    values: list[AttributeValueOut] = []


class CardSupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_name: str
    headquarter: str | None = None
    origin: str | None = None
    scale: str | None = None
    main_products: str | None = None
    overseas_track_record: str | None = None
    linked_supplier_id: int | None = None
    country_code: str | None = None
    registration_no: str | None = None
    review_status: str
    display_order: int


class CardCertificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cert_name: str
    applicable_market: str | None = None
    source: str
    credibility: str | None = None
    verify_status: str
    note: str | None = None
    display_order: int


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name_zh: str
    name_en: str | None = None
    display_order: int
    status: str


class CardOut(BaseModel):
    """资料卡完整内容(主表 + 卡级元数据 + B 层属性 + 厂商/认证子表)。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    category: CategoryOut

    # A 层字段(原样存储内容)
    field_1_definition: str | None = None
    field_2_tech_params: str | None = None
    field_3_spec_scene: str | None = None
    field_4_origin: Any | None = None
    field_7_cost: Any | None = None
    field_9_logistics: str | None = None
    field_10_risk: Any | None = None

    # 卡级元数据
    confidence_marks: dict[str, Any] | None = None
    snapshot_at: datetime | None = None
    version: str
    review_status: str

    # B 层属性维度 + 枚举值(独立字段,本期不与字段 2/3 拼接)
    attributes: list[AttributeOut] = []

    # 子表
    suppliers: list[CardSupplierOut] = []
    certifications: list[CardCertificationOut] = []
