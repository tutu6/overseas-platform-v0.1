"""主线一品类资料卡路由 /api/v1/catalog/*(工单 17 · Step 3)。

端点:
- GET /catalog/cards/{category_code}    按品类编码读资料卡

权限点:catalog:read(BUYER / OPERATOR 持有;SUPPLIER / ADMIN 不持有 → 403)。
纯读接口,不写审计(对齐 CLAUDE.md)。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import CurrentUser
from app.core.exceptions import success
from app.db.session import get_db
from app.rbac.constants import Permissions
from app.rbac.guards import require_permission
from app.services import catalog as catalog_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get(
    "/cards/{category_code}",
    summary="按品类编码读资料卡(主表 + B 层属性 + 厂商/认证子表)",
)
async def get_catalog_card(
    category_code: str = Path(
        ..., min_length=1, max_length=32, description="品类业务编码(如 aluminum-coil)"
    ),
    current: CurrentUser = Depends(require_permission(Permissions.CATALOG_READ)),
    db: AsyncSession = Depends(get_db),
):
    card = await catalog_service.get_card_by_category_code(db, category_code)
    return success(card.model_dump(mode="json"))
