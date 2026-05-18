"""Trace ID 中间件。

每个请求:
- 从 `X-Trace-Id` 头读取,缺失则生成 UUID
- 写入 request.state 与 contextvar(供日志/审计读取)
- 在响应头回写 `X-Trace-Id`
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.audit.context import set_trace_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())
        request.state.trace_id = trace_id
        set_trace_id(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response
