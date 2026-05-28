"""drop legacy categories table

Revision ID: 20260528_0010
Revises: 20260526_0009
Create Date: 2026-05-28

主线一(品类资料卡)启动前的清理:旧三级分类(`categories` 表)封存与下线。

- 旧实现完整封存在 archive 分支:`archive/legacy-3level-category`
- 移除范围:`Category` ORM/service/api、前端 cascader/hook/api/demo 页、
  Excel 批量导入脚本(`scripts/import_categories.py`)及其测试。
- 本 migration 仅 drop 旧表;新主线一品类相关表由后续 migration 单独创建。

破坏性 migration:含 `drop_table`,需要 commit message 标注
`[allow-destructive-migration]` 以通过 CI 拦截。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260528_0010"
down_revision: Union[str, None] = "20260526_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_categories_level_active_sort", table_name="categories")
    op.drop_index("ix_categories_parent_level", table_name="categories")
    op.drop_table("categories")


def downgrade() -> None:
    # 回滚仅恢复表结构(空表),不恢复历史数据;历史数据需从 archive 分支或 pg_dump 备份恢复。
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name_zh", sa.String(length=128), nullable=False),
        sa.Column("name_en", sa.String(length=128), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("parent_code", sa.String(length=16), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_categories_code"),
        sa.CheckConstraint("level IN (1, 2, 3)", name="ck_categories_level"),
        sa.ForeignKeyConstraint(
            ["parent_code"],
            ["categories.code"],
            name="fk_categories_parent_code",
        ),
    )
    op.create_index(
        "ix_categories_parent_level",
        "categories",
        ["parent_code", "level"],
    )
    op.create_index(
        "ix_categories_level_active_sort",
        "categories",
        ["level", "is_active", "sort_order"],
    )
