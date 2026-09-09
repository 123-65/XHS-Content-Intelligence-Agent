import json
from abc import ABC, abstractmethod
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.llm.cost import estimate_cost
from app.llm.errors import LLMResponseError
from app.schemas.llm import LLMResult, LLMStructuredResult, LLMUsage

T = TypeVar("T", bound=BaseModel)


class BaseLLMProvider(ABC):
    """LLM Provider 基础抽象。"""

    name: str = "base"
    is_mock: bool = False

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        """初始化 Provider 配置。"""
        self.api_key = api_key
        self.base_url = base_url
        self.model = model or settings.llm_model

    @abstractmethod
    def available(self) -> bool:
        """判断 Provider 当前是否可用。"""
        raise NotImplementedError

    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: str | None = None, model: str | None = None) -> LLMResult:
        """生成普通文本。"""
        raise NotImplementedError

    @abstractmethod
    def generate_structured(self, prompt: str, schema_model: type[T], system_prompt: str | None = None, model: str | None = None) -> LLMStructuredResult:
        """生成结构化结果。"""
        raise NotImplementedError

    def health(self) -> dict:
        """返回 Provider 健康状态。"""
        return {"active_provider": self.name, "model": self.model, "available": self.available(), "is_mock": self.is_mock}


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI-compatible LLM Provider。"""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        """初始化 OpenAI-compatible Provider。"""
        super().__init__(api_key, base_url, model)
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=settings.llm_timeout_seconds) if self.api_key else None

    def available(self) -> bool:
        """判断 OpenAI-compatible Provider 是否具备调用配置。"""
        return bool(self.api_key and self.base_url and self.model)

    @retry(stop=stop_after_attempt(settings.llm_max_retries), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def generate_text(self, prompt: str, system_prompt: str | None = None, model: str | None = None) -> LLMResult:
        """调用 OpenAI-compatible 接口生成普通文本。"""
        selected_model = model or self.model
        try:
            response = self.client.chat.completions.create(model=selected_model, messages=self._messages(prompt, system_prompt))
        except Exception as exc:
            raise LLMResponseError(f"LLM text call failed: {exc}") from exc
        usage = self._usage(response)
        return LLMResult(
            text=response.choices[0].message.content or "",
            model=selected_model,
            provider=self.name,
            usage=usage,
            estimated_cost=estimate_cost(usage),
            raw_response_id=getattr(response, "id", None),
            is_mock=False,
        )

    @retry(stop=stop_after_attempt(settings.llm_max_retries), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
    def generate_structured(self, prompt: str, schema_model: type[T], system_prompt: str | None = None, model: str | None = None) -> LLMStructuredResult:
        """调用 OpenAI-compatible 接口生成结构化 JSON。"""
        selected_model = model or self.model
        json_prompt = self._json_prompt(prompt, schema_model.model_json_schema())
        try:
            response = self.client.chat.completions.create(
                model=selected_model,
                messages=self._messages(json_prompt, system_prompt),
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            raise LLMResponseError(f"LLM structured call failed: {exc}") from exc
        text = response.choices[0].message.content or ""
        usage = self._usage(response)
        return LLMStructuredResult(
            data=self._parse(text, schema_model),
            text=text,
            model=selected_model,
            provider=self.name,
            usage=usage,
            estimated_cost=estimate_cost(usage),
            raw_response_id=getattr(response, "id", None),
            is_mock=False,
        )

    def _messages(self, prompt: str, system_prompt: str | None = None) -> list[dict]:
        """构造 Chat Completion 消息。"""
        return [*([{"role": "system", "content": system_prompt}] if system_prompt else []), {"role": "user", "content": prompt}]

    def _json_prompt(self, prompt: str, schema: dict) -> str:
        """向 Prompt 追加 JSON Schema 约束。"""
        return (
            "Return strict JSON only. Do not return Markdown or explanatory text.\n\n"
            f"User task:\n{prompt}\n\n"
            f"The output must satisfy this JSON Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
            "Rules:\n1. Return exactly one valid JSON object.\n2. Do not wrap the output in a code block.\n3. Do not return the schema itself.\n4. Fill every required field according to the schema.\n"
        )

    def _parse(self, text: str, schema_model: type[T]) -> T:
        """解析并校验结构化输出。"""
        try:
            return schema_model.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMResponseError(f"LLM JSON parse failed: {exc}; raw output: {text[:500]}") from exc

    def _usage(self, response) -> LLMUsage:
        """提取 OpenAI-compatible usage。"""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        return LLMUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=getattr(usage, "total_tokens", 0) or prompt_tokens + completion_tokens)
