from typing import Any

from pydantic import BaseModel

class ApiResponse(BaseModel):
    """统一响应模型。"""

    code: int = 0
    message: str = "success"
    data: Any= None

def success(data: Any = None, message: str = "success") -> ApiResponse:
    """成功响应。"""
    return ApiResponse(code=0, message=message, data=data)
def fail(code: int = 1, message: str = "failure", data: Any = None) -> ApiResponse:
    """失败响应。"""
    return ApiResponse(code=code, message=message, data=data)