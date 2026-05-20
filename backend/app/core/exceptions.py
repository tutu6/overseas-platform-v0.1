"""业务异常 + 统一响应格式。

业务码约定:
- 0       成功
- 4xxxx   客户端错误(40001 凭证错误,40002 限流,40003 权限不足 ...)
- 5xxxx   服务器错误
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class BusinessError(HTTPException):
    """所有业务异常的基类。"""

    def __init__(
        self,
        http_status: int,
        biz_code: int,
        message: str,
        data: Any = None,
    ):
        super().__init__(status_code=http_status, detail=message)
        self.biz_code = biz_code
        self.biz_message = message
        self.biz_data = data


class InvalidCredentialsError(BusinessError):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, 40001, message)


class TooManyAttemptsError(BusinessError):
    def __init__(self, message: str = "Too many failed attempts, account locked"):
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, 40002, message)


class PermissionDeniedError(BusinessError):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(status.HTTP_403_FORBIDDEN, 40003, message)


class NotAuthenticatedError(BusinessError):
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, 40004, message)


class AccountDisabledError(BusinessError):
    def __init__(self, message: str = "Account disabled"):
        super().__init__(status.HTTP_403_FORBIDDEN, 40005, message)


class ValidationFailedError(BusinessError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(status.HTTP_400_BAD_REQUEST, 40006, message)


class ConflictError(BusinessError):
    def __init__(self, message: str = "Resource conflict"):
        super().__init__(status.HTTP_409_CONFLICT, 40009, message)


class SupplierAlreadyRegisteredError(BusinessError):
    """供应商重复入驻(PRD v1.4 Δ9)。

    code=40901(数字),前端识别错误必须用数字比较,严禁字符串比较异常类名。
    message 沿用 PRD v1.3 §5.3 标准化文案,不暴露 owner / 公司名。
    """

    def __init__(
        self,
        message: str = "当前企业已在平台注册。如需加入,请联系您所在企业的平台管理员添加账号。",
    ):
        super().__init__(status.HTTP_409_CONFLICT, 40901, message)


class NotFoundError(BusinessError):
    def __init__(self, message: str = "Not found"):
        super().__init__(status.HTTP_404_NOT_FOUND, 40400, message)


def success(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}
