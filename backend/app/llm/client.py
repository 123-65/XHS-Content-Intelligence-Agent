from time import perf_counter
from typing import TypeVar

from pydantic import BaseModel

from app.context.context_slots import BuiltContext
from app.llm.errors import LLMError
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.router import build_llm_provider, configured_provider_name
from app.schemas.llm import LLMResult, LLMStructuredResult

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified LLM client. Business code must call this class only."""

    def __init__(self, provider_name: str | None = None):
        """Initialize and select the configured provider, with Mock fallback."""
        self.requested_provider = configured_provider_name(provider_name)
        self.provider_impl = build_llm_provider(self.requested_provider)
        self.initial_fallback_from: str | None = None
        if self.provider_impl.is_mock and self.requested_provider != "mock":
            self.initial_fallback_from = self.requested_provider
        if not self.provider_impl.available():
            self.initial_fallback_from = self.requested_provider
            self.provider_impl = MockLLMProvider()
        self.model = self.provider_impl.model
        self.provider = self.provider_impl.name
        self.is_mock = self.provider_impl.is_mock

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMResult:
        """Generate text and fall back to Mock when the real provider fails."""
        started_at = perf_counter()
        fallback_used = self.provider_impl.is_mock and self.requested_provider != "mock"
        try:
            result = self.provider_impl.generate_text(prompt, system_prompt, model)
            return self._with_metadata(result, started_at, prompt_key, prompt_version, fallback_used, self.initial_fallback_from)
        except LLMError as exc:
            return self._mock_text(prompt, system_prompt, model, started_at, prompt_key, prompt_version, str(exc))
        except Exception as exc:
            return self._mock_text(prompt, system_prompt, model, started_at, prompt_key, prompt_version, str(exc))

    def generate_structured(
        self,
        prompt: str,
        schema_model: type[T],
        system_prompt: str | None = None,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMStructuredResult:
        """Generate structured JSON and fall back to Mock when the real provider fails."""
        started_at = perf_counter()
        fallback_used = self.provider_impl.is_mock and self.requested_provider != "mock"
        try:
            result = self.provider_impl.generate_structured(prompt, schema_model, system_prompt, model)
            return self._with_metadata(result, started_at, prompt_key, prompt_version, fallback_used, self.initial_fallback_from)
        except LLMError as exc:
            return self._mock_structured(prompt, schema_model, system_prompt, model, started_at, prompt_key, prompt_version, str(exc))
        except Exception as exc:
            return self._mock_structured(prompt, schema_model, system_prompt, model, started_at, prompt_key, prompt_version, str(exc))

    def generate_text_with_context(
        self,
        context: BuiltContext,
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMResult:
        """Generate text using a governed context snapshot."""
        return self.generate_text(context.user_prompt, context.system_prompt, model, prompt_key, prompt_version)

    def generate_structured_with_context(
        self,
        context: BuiltContext,
        schema_model: type[T],
        model: str | None = None,
        prompt_key: str | None = None,
        prompt_version: str | None = None,
    ) -> LLMStructuredResult:
        """Generate structured output using a governed context snapshot."""
        return self.generate_structured(context.user_prompt, schema_model, context.system_prompt, model, prompt_key, prompt_version)

    def health(self) -> dict:
        """Return current active provider health."""
        return self.provider_impl.health()

    def _mock_text(
        self,
        prompt: str,
        system_prompt: str | None,
        model: str | None,
        started_at: float,
        prompt_key: str | None,
        prompt_version: str | None,
        error_message: str,
    ) -> LLMResult:
        result = MockLLMProvider().generate_text(prompt, system_prompt, model)
        return self._with_metadata(result, started_at, prompt_key, prompt_version, True, self.provider_impl.name, error_message)

    def _mock_structured(
        self,
        prompt: str,
        schema_model: type[T],
        system_prompt: str | None,
        model: str | None,
        started_at: float,
        prompt_key: str | None,
        prompt_version: str | None,
        error_message: str,
    ) -> LLMStructuredResult:
        result = MockLLMProvider().generate_structured(prompt, schema_model, system_prompt, model)
        return self._with_metadata(result, started_at, prompt_key, prompt_version, True, self.provider_impl.name, error_message)

    def _with_metadata(
        self,
        result,
        started_at: float,
        prompt_key: str | None,
        prompt_version: str | None,
        fallback_used: bool,
        fallback_from: str | None = None,
        error_message: str | None = None,
    ):
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
