from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.response import fail, success
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.llm.router import llm_health
from app.schemas.llm_test import LLMTestAnalysisResult

router = APIRouter(prefix="/llm", tags=["大模型调用"])


def _llm_error(exc: LLMError) -> JSONResponse:
    """返回模型调用错误响应。"""
    return JSONResponse(status_code=500, content=fail(code=500, message=str(exc)).model_dump())


@router.get("/health")
def get_llm_health():
    """获取 LLM Provider 健康状态。"""
    return success(llm_health())


@router.post("/test-text")
def test_llm_text(prompt: str = Query(...)):
    """测试普通文本模型调用。"""
    try:
        client = LLMClient()
        result = client.generate_text(
            prompt=prompt,
            system_prompt="你是一个小红书内容增长分析助手，回答要简洁、具体、可执行。",
        )
        return success(result.model_dump())
    except LLMError as exc:
        return _llm_error(exc)


@router.post("/test-structured")
def test_llm_structured(prompt: str = Query(...)):
    """测试结构化模型调用。"""
    try:
        client = LLMClient()
        result = client.generate_structured(
            prompt=prompt,
            schema_model=LLMTestAnalysisResult,
            system_prompt="你是一个小红书内容增长分析助手，请严格输出 json。",
        )
        data = result.model_dump()
        data["data"] = result.data.model_dump()
        return success(data)
    except LLMError as exc:
        return _llm_error(exc)
