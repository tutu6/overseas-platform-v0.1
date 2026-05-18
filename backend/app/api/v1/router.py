"""聚合所有 v1 路由。"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin_users, auth, test_rbac

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(test_rbac.router)
