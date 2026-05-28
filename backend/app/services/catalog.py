"""主线一品类资料卡 service(工单 17 · Step 3)。

只读 service:按品类编码 一次性 组装完整资料卡(主表 + B 层属性
+ 枚举值 + 厂商子表 + 认证子表)。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models import (
    CatalogAttribute,
    CatalogAttributeValue,
    CatalogCard,
    CatalogCardCertification,
    CatalogCardSupplier,
    CatalogCategory,
)
from app.schemas.catalog import (
    AttributeOut,
    AttributeValueOut,
    CardCertificationOut,
    CardOut,
    CardSupplierOut,
    CategoryOut,
)


async def get_card_by_category_code(
    db: AsyncSession, category_code: str
) -> CardOut:
    """按品类编码读完整资料卡。

    流程:
    1. 查品类(不存在 → 404)
    2. 查资料卡(不存在 → 404)
    3. 查 B 层属性维度 + 枚举值(按 display_order/value_order 排序)
    4. 查厂商子表 + 认证子表(按 display_order 排序)
    5. 组装 CardOut
    """
    # 1. 品类
    cat_row = await db.execute(
        select(CatalogCategory).where(CatalogCategory.code == category_code)
    )
    category = cat_row.scalar_one_or_none()
    if category is None:
        raise NotFoundError(f"Category '{category_code}' not found")

    # 2. 主卡
    card_row = await db.execute(
        select(CatalogCard).where(CatalogCard.category_id == category.id)
    )
    card = card_row.scalar_one_or_none()
    if card is None:
        raise NotFoundError(
            f"Card for category '{category_code}' not found"
        )

    # 3. 属性维度(一次查,在应用层 group 枚举值)
    attrs_rows = await db.execute(
        select(CatalogAttribute)
        .where(CatalogAttribute.category_id == category.id)
        .order_by(CatalogAttribute.display_order, CatalogAttribute.id)
    )
    attributes = attrs_rows.scalars().all()
    attr_ids = [a.id for a in attributes]

    values_by_attr: dict[int, list[CatalogAttributeValue]] = {
        aid: [] for aid in attr_ids
    }
    if attr_ids:
        val_rows = await db.execute(
            select(CatalogAttributeValue)
            .where(CatalogAttributeValue.attr_id.in_(attr_ids))
            .order_by(
                CatalogAttributeValue.attr_id,
                CatalogAttributeValue.value_order,
                CatalogAttributeValue.id,
            )
        )
        for v in val_rows.scalars().all():
            values_by_attr[v.attr_id].append(v)

    attribute_outs: list[AttributeOut] = []
    for a in attributes:
        attr_out = AttributeOut.model_validate(a)
        attr_out.values = [
            AttributeValueOut.model_validate(v) for v in values_by_attr[a.id]
        ]
        attribute_outs.append(attr_out)

    # 4. 厂商
    suppliers_rows = await db.execute(
        select(CatalogCardSupplier)
        .where(CatalogCardSupplier.card_id == card.id)
        .order_by(CatalogCardSupplier.display_order, CatalogCardSupplier.id)
    )
    suppliers = [
        CardSupplierOut.model_validate(s) for s in suppliers_rows.scalars().all()
    ]

    # 5. 认证
    certs_rows = await db.execute(
        select(CatalogCardCertification)
        .where(CatalogCardCertification.card_id == card.id)
        .order_by(
            CatalogCardCertification.display_order,
            CatalogCardCertification.id,
        )
    )
    certifications = [
        CardCertificationOut.model_validate(c)
        for c in certs_rows.scalars().all()
    ]

    # 6. 组装
    return CardOut(
        id=card.id,
        category=CategoryOut.model_validate(category),
        field_1_definition=card.field_1_definition,
        field_2_tech_params=card.field_2_tech_params,
        field_3_spec_scene=card.field_3_spec_scene,
        field_4_origin=card.field_4_origin,
        field_7_cost=card.field_7_cost,
        field_9_logistics=card.field_9_logistics,
        field_10_risk=card.field_10_risk,
        confidence_marks=card.confidence_marks,
        snapshot_at=card.snapshot_at,
        version=card.version,
        review_status=card.review_status,
        attributes=attribute_outs,
        suppliers=suppliers,
        certifications=certifications,
    )
