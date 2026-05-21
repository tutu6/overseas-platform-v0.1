"""商品分类 service:查全表 + 内存建树(对齐 PRD §5.4)。

性能预期:全表 < 2000 条,不加缓存,每次查全表 + 在应用层组装。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category
from app.schemas.category import CategoryNode, CategoryTreeNode


async def list_flat(
    db: AsyncSession,
    *,
    level: int | None = None,
    parent_code: str | None = None,
    is_active: bool | None = True,
) -> list[CategoryNode]:
    """扁平列表,按 (level, sort_order, code) 稳定排序。"""
    stmt = select(Category)
    if is_active is not None:
        stmt = stmt.where(Category.is_active == is_active)
    if level is not None:
        stmt = stmt.where(Category.level == level)
    if parent_code is not None:
        stmt = stmt.where(Category.parent_code == parent_code)
    stmt = stmt.order_by(
        Category.level, Category.parent_code, Category.sort_order, Category.code
    )

    rows = (await db.execute(stmt)).scalars().all()
    return [CategoryNode.model_validate(r) for r in rows]


async def get_tree(
    db: AsyncSession,
    *,
    is_active: bool | None = True,
) -> list[CategoryTreeNode]:
    """三层嵌套树,按 (sort_order, code) 排序。"""
    stmt = select(Category)
    if is_active is not None:
        stmt = stmt.where(Category.is_active == is_active)
    stmt = stmt.order_by(
        Category.level, Category.parent_code, Category.sort_order, Category.code
    )

    rows = (await db.execute(stmt)).scalars().all()

    # 一次组装:code → TreeNode,parent_code → 接到对应父节点 children
    nodes_by_code: dict[str, CategoryTreeNode] = {}
    roots: list[CategoryTreeNode] = []
    pending_children: list[tuple[str, CategoryTreeNode]] = []

    for r in rows:
        node = CategoryTreeNode(
            id=r.id,
            code=r.code,
            name_zh=r.name_zh,
            name_en=r.name_en,
            level=r.level,
            children=[],
        )
        nodes_by_code[r.code] = node
        if r.parent_code is None:
            roots.append(node)
        else:
            pending_children.append((r.parent_code, node))

    for parent_code, child in pending_children:
        parent = nodes_by_code.get(parent_code)
        if parent is None:
            # 父节点被过滤掉(如 is_active=false),挂到根作为孤儿
            # 实际不会发生,因为 is_active 是逐层一致的;真出现就当根处理
            roots.append(child)
        else:
            parent.children.append(child)

    return roots
