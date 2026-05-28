"""create catalog (main line 1) tables

Revision ID: 20260528_0011
Revises: 20260528_0010
Create Date: 2026-05-28

主线一品类资料卡 — 数据建模落地。建 6 张新表:

B 层(EAV 三表,定义品类与属性):
- catalog_category            品类(分类树根节点,1 级)
- catalog_attribute           属性维度(牌号、厚度、状态…)
- catalog_attribute_value     枚举值(1050、H24、彩涂…)

A 层(资料卡内容):
- catalog_card                资料卡主表(一品类一卡,字段 1/2/3/4/7/9/10)
- catalog_card_supplier       字段 5 厂商子表
- catalog_card_certification  字段 8 认证子表

非破坏性 migration(仅 create_table + create_index),不触发 CI 拦截。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0011"
down_revision: Union[str, None] = "20260528_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===== B 层 =====
    op.create_table(
        "catalog_category",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name_zh", sa.String(length=128), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=True),
        sa.Column(
            "display_order", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_catalog_category_code"),
    )
    op.create_index(
        "ix_catalog_category_status_order",
        "catalog_category",
        ["status", "display_order"],
    )

    op.create_table(
        "catalog_attribute",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("attr_code", sa.String(length=32), nullable=False),
        sa.Column("attr_name", sa.String(length=64), nullable=False),
        sa.Column("attr_type", sa.String(length=16), nullable=False),
        sa.Column("attr_unit", sa.String(length=16), nullable=True),
        sa.Column("min_value", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("max_value", sa.Numeric(precision=15, scale=4), nullable=True),
        sa.Column("decimal_places", sa.SmallInteger(), nullable=True),
        sa.Column(
            "is_filterable",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_variant_axis",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "display_order", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["catalog_category.id"],
            name="fk_catalog_attribute_category",
        ),
        sa.UniqueConstraint(
            "category_id", "attr_code", name="uq_catalog_attribute_category_code"
        ),
    )
    op.create_index(
        "ix_catalog_attribute_category_order",
        "catalog_attribute",
        ["category_id", "display_order"],
    )

    op.create_table(
        "catalog_attribute_value",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("attr_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(length=64), nullable=False),
        sa.Column(
            "value_order", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["attr_id"],
            ["catalog_attribute.id"],
            name="fk_catalog_attribute_value_attr",
        ),
        sa.UniqueConstraint(
            "attr_id", "value", name="uq_catalog_attribute_value_attr_value"
        ),
    )
    op.create_index(
        "ix_catalog_attribute_value_attr_order",
        "catalog_attribute_value",
        ["attr_id", "value_order"],
    )

    # ===== A 层 =====
    op.create_table(
        "catalog_card",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("field_1_definition", sa.Text(), nullable=True),
        sa.Column("field_2_tech_params", sa.Text(), nullable=True),
        sa.Column("field_3_spec_scene", sa.Text(), nullable=True),
        sa.Column(
            "field_4_origin",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "field_7_cost",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("field_9_logistics", sa.Text(), nullable=True),
        sa.Column(
            "field_10_risk",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "confidence_marks",
            sa.dialects.postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("snapshot_at", sa.DateTime(), nullable=True),
        sa.Column(
            "version", sa.String(length=32), nullable=False, server_default="v0.1"
        ),
        sa.Column(
            "review_status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["catalog_category.id"],
            name="fk_catalog_card_category",
        ),
        sa.UniqueConstraint("category_id", name="uq_catalog_card_category"),
    )

    op.create_table(
        "catalog_card_supplier",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("supplier_name", sa.String(length=200), nullable=False),
        sa.Column("headquarter", sa.String(length=100), nullable=True),
        sa.Column("origin", sa.String(length=100), nullable=True),
        sa.Column("scale", sa.String(length=200), nullable=True),
        sa.Column("main_products", sa.Text(), nullable=True),
        sa.Column("overseas_track_record", sa.Text(), nullable=True),
        sa.Column("linked_supplier_id", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("registration_no", sa.String(length=100), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=16),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "display_order", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["catalog_card.id"],
            name="fk_catalog_card_supplier_card",
        ),
        sa.ForeignKeyConstraint(
            ["linked_supplier_id"],
            ["supplier_organizations.id"],
            name="fk_catalog_card_supplier_linked",
        ),
    )
    op.create_index(
        "ix_catalog_card_supplier_card_order",
        "catalog_card_supplier",
        ["card_id", "display_order"],
    )
    op.create_index(
        "ix_catalog_card_supplier_country_regno",
        "catalog_card_supplier",
        ["country_code", "registration_no"],
    )

    op.create_table(
        "catalog_card_certification",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("cert_name", sa.String(length=100), nullable=False),
        sa.Column("applicable_market", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("credibility", sa.String(length=16), nullable=True),
        sa.Column(
            "verify_status",
            sa.String(length=16),
            nullable=False,
            server_default="unverified",
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "display_order", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["catalog_card.id"],
            name="fk_catalog_card_cert_card",
        ),
    )
    op.create_index(
        "ix_catalog_card_cert_card_order",
        "catalog_card_certification",
        ["card_id", "display_order"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_catalog_card_cert_card_order", table_name="catalog_card_certification"
    )
    op.drop_table("catalog_card_certification")

    op.drop_index(
        "ix_catalog_card_supplier_country_regno", table_name="catalog_card_supplier"
    )
    op.drop_index(
        "ix_catalog_card_supplier_card_order", table_name="catalog_card_supplier"
    )
    op.drop_table("catalog_card_supplier")

    op.drop_table("catalog_card")

    op.drop_index(
        "ix_catalog_attribute_value_attr_order",
        table_name="catalog_attribute_value",
    )
    op.drop_table("catalog_attribute_value")

    op.drop_index(
        "ix_catalog_attribute_category_order", table_name="catalog_attribute"
    )
    op.drop_table("catalog_attribute")

    op.drop_index(
        "ix_catalog_category_status_order", table_name="catalog_category"
    )
    op.drop_table("catalog_category")
