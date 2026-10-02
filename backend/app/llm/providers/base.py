import json
from abc import ABC, abstractmethod
from time import perf_counter
from typing import TypeVar

import httpx
from openai import APITimeoutError, OpenAI
from pydantic import BaseModel, ValidationError
from tenacity import Retrying, retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.llm.cost import estimate_cost
from app.llm.errors import LLMResponseError, LLMSchemaValidationError, LLMTimeoutError
from app.llm.evidence import safe_value, validation_summary
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
    def generate_structured(self, prompt: str, schema_model: type[T], system_prompt: str | None = None, model: str | None = None, extra_body: dict | None = None, timeout_seconds: float | None = None) -> LLMStructuredResult:
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
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        ) if self.api_key else None

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

    def generate_structured(self, prompt: str, schema_model: type[T], system_prompt: str | None = None, model: str | None = None, extra_body: dict | None = None, timeout_seconds: float | None = None) -> LLMStructuredResult:
        """调用 OpenAI-compatible 接口生成结构化 JSON。"""
        selected_model = model or self.model
        json_prompt = self._json_prompt(prompt, schema_model.model_json_schema())
        attempts: list[dict] = []
        retrying = Retrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_not_exception_type(LLMTimeoutError),
            reraise=True,
        )
        try:
            for attempt in retrying:
                with attempt:
                    number = attempt.retry_state.attempt_number
                    started = perf_counter()
                    text = ""
                    try:
                        request_options = {
                            "model": selected_model,
                            "messages": self._messages(json_prompt, system_prompt),
                            "response_format": {"type": "json_object"},
                        }
                        if extra_body is not None:
                            request_options["extra_body"] = extra_body
                        if timeout_seconds is not None:
                            request_options["timeout"] = timeout_seconds
                        response = self.client.chat.completions.create(**request_options)
                    except Exception as exc:
                        wrapped = (
                            LLMTimeoutError("LLM request exceeded its configured deadline.")
                            if isinstance(exc, (APITimeoutError, httpx.TimeoutException, TimeoutError))
                            else LLMResponseError(f"LLM structured call failed: {exc}")
                        )
                        attempts.append(self._attempt(number, selected_model, "PROVIDER_FAILED", "PROVIDER_PARSE", wrapped, None, started))
                        raise wrapped from exc
                    text = response.choices[0].message.content or ""
                    try:
                        parsed = self._parse(text, schema_model)
                    except LLMSchemaValidationError as exc:
                        attempts.append(self._attempt(number, selected_model, "VALIDATION_FAILED", getattr(exc, "validation_layer", "PYDANTIC_SCHEMA"), exc, getattr(exc, "candidate", None), started))
                        raise
                    usage = self._usage(response)
                    attempts.append(self._attempt(number, selected_model, "SUCCESS", None, None, parsed.model_dump(mode="json"), started))
                    return LLMStructuredResult(
                        data=parsed, text=text, model=selected_model, provider=self.name, usage=usage,
                        estimated_cost=estimate_cost(usage), raw_response_id=getattr(response, "id", None),
                        is_mock=False, attempt_evidence=attempts,
                    )
        except Exception as exc:
            setattr(exc, "attempt_evidence", attempts)
            raise

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
            candidate = json.loads(text)
        except json.JSONDecodeError as exc:
            error = LLMSchemaValidationError("LLM output is not valid JSON")
            error.validation_layer = "PROVIDER_PARSE"
            error.validation_summary = validation_summary(exc)
            error.candidate = None
            raise error from exc
        try:
            return schema_model.model_validate(candidate)
        except ValidationError as exc:
            error = LLMSchemaValidationError("LLM output does not satisfy the requested schema")
            error.validation_layer = "PYDANTIC_SCHEMA"
            error.validation_summary = validation_summary(exc, candidate)
            error.candidate = candidate
            raise error from exc

    def _attempt(self, number, model, status, layer, exc, candidate, started):
        timeout = getattr(exc, "code", None) == "LLM_TIMEOUT"
        return {
            "provider": self.name,
            "model": model,
            "attempt_number": number,
            "attempt_total": settings.llm_max_retries,
            "attempt_status": status,
            "failure_stage": "STRUCTURED_GENERATION" if status != "SUCCESS" else None,
            "validation_layer": layer,
            "validation_summary": getattr(exc, "validation_summary", validation_summary(exc, candidate)) if exc else {},
            "structured_candidate": safe_value(candidate),
            "retryable": status != "SUCCESS" and not timeout,
            "retry_exhausted": status != "SUCCESS" and (timeout or number == settings.llm_max_retries),
            "final_error_code": "LLM_TIMEOUT" if timeout else "LLM_STRUCTURED_VALIDATION_FAILED" if status == "VALIDATION_FAILED" else "LLM_PROVIDER_UNAVAILABLE" if status == "PROVIDER_FAILED" else None,
            "latency_ms": max(0, int((perf_counter() - started) * 1000)),
        }

    def _usage(self, response) -> LLMUsage:
        """提取 OpenAI-compatible usage。"""
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        return LLMUsage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=getattr(usage, "total_tokens", 0) or prompt_tokens + completion_tokens)
