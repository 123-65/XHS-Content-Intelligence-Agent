from time import perf_counter
from typing import TypeVar

from pydantic import BaseModel

from app.core.config import settings
from app.context.context_slots import BuiltContext
from app.llm.errors import LLMError
from app.llm.evidence import PromptRunEvidenceRecorder, safe_value, validation_summary
from app.llm.router import build_llm_provider, configured_provider_name
from app.schemas.llm import LLMResult, LLMStructuredResult
from app.schemas.provider_status import ProviderErrorCode

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """统一 LLM 客户端。业务代码只允许调用此类。"""

    def __init__(self, provider_name: str | None = None, evidence_recorder=None):
        """初始化真实 LLM Provider；不提供 Mock 或隐式降级。"""
        self.requested_provider = configured_provider_name(provider_name)
        self.provider_impl = build_llm_provider(self.requested_provider)
        if not self.provider_impl.available():
            raise LLMError(f"{ProviderErrorCode.LLM_CONFIG_MISSING.value}: provider {self.requested_provider} is not configured")
        self.model = self.provider_impl.model
        self.provider = self.provider_impl.name
        self.is_mock = self.provider_impl.is_mock
        self.evidence_recorder = evidence_recorder or PromptRunEvidenceRecorder()
        self._last_structured_context: dict | None = None

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMResult:
        """生成文本；真实 Provider 失败时抛出错误，不自动回退 Mock。"""
        started_at = perf_counter()
        try:
            result = self.provider_impl.generate_text(prompt, system_prompt, model)
            return self._with_metadata(result, started_at, prompt_key, prompt_version, False)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"{ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value}: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        schema_model: type[T],
        system_prompt: str | None = None,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
        extra_body: dict | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMStructuredResult:
        """生成结构化 JSON；真实 Provider 失败时抛出错误，不自动回退 Mock。"""
        started_at = perf_counter()
        context = {
            "provider": self.provider,
            "model": model or self.model,
            "prompt_key": prompt_key,
            "prompt_version": prompt_version,
            "schema_name": schema_model.__name__,
        }
        self._last_structured_context = context
        try:
            if extra_body is None and timeout_seconds is None:
                result = self.provider_impl.generate_structured(prompt, schema_model, system_prompt, model)
            else:
                result = self.provider_impl.generate_structured(
                    prompt, schema_model, system_prompt, model,
                    extra_body=extra_body, timeout_seconds=timeout_seconds,
                )
            self._record_attempts(result.attempt_evidence, context)
            return self._with_metadata(result, started_at, prompt_key, prompt_version, False)
        except LLMError as exc:
            self._record_attempts(getattr(exc, "attempt_evidence", []), context)
            raise
        except Exception as exc:
            raise LLMError(f"{ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value}: {exc}") from exc

    def record_business_validation_failure(
        self,
        exc: Exception,
        candidate,
        *,
        validation_layer="POST_PARSE_BUSINESS_VALIDATION",
        attempt_number: int = 1,
        attempt_total: int | None = None,
        retry_exhausted: bool = True,
    ):
        """Record deterministic validation after provider parsing without exposing source content."""
        context = self._last_structured_context or {
            "provider": self.provider, "model": self.model, "prompt_key": None,
            "prompt_version": None, "schema_name": type(candidate).__name__,
        }
        self.evidence_recorder.record({
            **context,
            "attempt_number": attempt_number,
            "attempt_total": attempt_total or settings.llm_max_retries,
            "attempt_status": "VALIDATION_FAILED",
            "failure_stage": "POST_PARSE_VALIDATION",
            "validation_layer": validation_layer,
            "validation_summary": validation_summary(exc, candidate),
            "structured_candidate": safe_value(candidate),
            "retryable": not retry_exhausted,
            "retry_exhausted": retry_exhausted,
            "final_error_code": "VALIDATION_ERROR",
            "latency_ms": 0,
        })

    def _record_attempts(self, attempts, context):
        for item in attempts:
            self.evidence_recorder.record({**context, **item})
    def generate_text_with_context(
        self,
        context: BuiltContext,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMResult:
        """基于受治理的上下文快照生成文本。"""
        return self.generate_text(context.user_prompt, context.system_prompt, model, prompt_key, prompt_version)

    def generate_structured_with_context(
        self,
        context: BuiltContext,
        schema_model: type[T],
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMStructuredResult:
        """基于受治理的上下文快照生成结构化输出。"""
        return self.generate_structured(context.user_prompt, schema_model, context.system_prompt, model, prompt_key, prompt_version)

    def health(self) -> dict:
        """返回当前生效 Provider 的健康状态。"""
        return self.provider_impl.health()

    def _with_metadata(
        self,
        result,
        started_at: float,
        prompt_key: str | None,
        prompt_version: str | None,
        fallback_used: bool = False,
        fallback_from: str | None = None,
        error_message: str | None = None,
    ):
        """为 LLM 结果补充元数据：耗时、prompt 标识、Provider 信息。"""
        latency_ms = max(0, int((perf_counter() - started_at) * 1000))
        return result.model_copy(
            update={
                "latency_ms": latency_ms,
                "prompt_key": prompt_key,
                "prompt_version": prompt_version,
                "fallback_used": fallback_used,
                "fallback_from": fallback_from,
                "error_message": error_message,
            }
        )
