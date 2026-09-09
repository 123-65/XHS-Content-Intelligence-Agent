from typing import TypeVar

from pydantic import BaseModel

from app.llm.mock_client import MockLLMClient
from app.llm.providers.base import BaseLLMProvider
from app.schemas.llm import LLMResult, LLMStructuredResult

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider。"""

    name = "mock"
    is_mock = True

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        """初始化 Mock Provider。"""
        super().__init__(api_key, base_url, model)
        self.client = MockLLMClient()
        self.model = self.client.model

    def available(self) -> bool:
        """Mock Provider 始终可用。"""
        return True

    def generate_text(self, prompt: str, system_prompt: str | None = None, model: str | None = None) -> LLMResult:
        """生成 Mock 文本。"""
        result = self.client.generate_text(prompt, system_prompt, model)
        return result.model_copy(update={"provider": self.name, "is_mock": True})

    def generate_structured(self, prompt: str, schema_model: type[T], system_prompt: str | None = None, model: str | None = None) -> LLMStructuredResult:
        """生成 Mock 结构化结果。"""
        result = self.client.generate_structured(prompt, schema_model, system_prompt, model)
        return result.model_copy(update={"provider": self.name, "is_mock": True})
