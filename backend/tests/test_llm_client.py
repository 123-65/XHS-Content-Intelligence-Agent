from app.llm.client import LLMClient
from app.llm.errors import LLMResponseError
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.router import llm_health
from app.schemas.llm import LLMResult, LLMStructuredResult, LLMUsage
from app.schemas.llm_test import LLMTestAnalysisResult


class FakeRealProvider:
    name = "qwen"
    is_mock = False
    model = "qwen-plus"

    def available(self) -> bool:
        return True

    def generate_text(self, prompt: str, system_prompt: str | None = None, model: str | None = None) -> LLMResult:
        return LLMResult(
            text="real provider text",
            model=model or self.model,
            provider=self.name,
            usage=LLMUsage(prompt_tokens=12, completion_tokens=8, total_tokens=20),
            estimated_cost=0,
            raw_response_id="fake-real-response",
            is_mock=False,
        )

    def generate_structured(self, prompt: str, schema_model, system_prompt: str | None = None, model: str | None = None) -> LLMStructuredResult:
        data = schema_model.model_validate({"summary": "real structured result", "suggestions": ["keep it concrete"], "score": 88})
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model=model or self.model,
            provider=self.name,
            usage=LLMUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
            estimated_cost=0,
            raw_response_id="fake-real-structured",
            is_mock=False,
        )

    def health(self) -> dict:
        return {"active_provider": self.name, "model": self.model, "available": True, "is_mock": False}


class FakeFailingProvider(FakeRealProvider):
    name = "deepseek"

    def generate_text(self, prompt: str, system_prompt: str | None = None, model: str | None = None) -> LLMResult:
        raise LLMResponseError("upstream timeout")

    def generate_structured(self, prompt: str, schema_model, system_prompt: str | None = None, model: str | None = None) -> LLMStructuredResult:
        raise LLMResponseError("upstream timeout")


def test_no_api_key_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "qwen")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: MockLLMProvider())

    result = LLMClient().generate_text("test prompt", prompt_key="unit_test", prompt_version="v1")

    assert result.provider == "mock"
    assert result.is_mock is True
    assert result.fallback_used is True
    assert result.fallback_from == "qwen"
    assert result.prompt_key == "unit_test"
    assert result.prompt_version == "v1"
    assert result.latency_ms >= 0


def test_configured_qwen_can_return_real_text(monkeypatch):
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "qwen")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: FakeRealProvider())

    result = LLMClient().generate_text("test prompt")

    assert result.text == "real provider text"
    assert result.provider == "qwen"
    assert result.model == "qwen-plus"
    assert result.is_mock is False
    assert result.fallback_used is False
    assert result.usage.total_tokens == 20


def test_provider_failure_records_error_and_fallback(monkeypatch):
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "deepseek")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: FakeFailingProvider())

    result = LLMClient().generate_text("test prompt")

    assert result.provider == "mock"
    assert result.is_mock is True
    assert result.fallback_used is True
    assert result.fallback_from == "deepseek"
    assert "upstream timeout" in (result.error_message or "")


def test_generate_structured_parses_real_provider_json(monkeypatch):
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "qwen")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: FakeRealProvider())

    result = LLMClient().generate_structured("structured prompt", LLMTestAnalysisResult)

    assert isinstance(result.data, LLMTestAnalysisResult)
    assert result.data.summary == "real structured result"
    assert result.data.score == 88
    assert result.provider == "qwen"


def test_provider_health_distinguishes_mock_fallback(monkeypatch):
    monkeypatch.setattr("app.llm.router.settings.llm_provider", "qwen")
    monkeypatch.setattr("app.llm.router.settings.llm_api_key", None)

    health = llm_health()

    assert health["requested_provider"] == "qwen"
    assert health["active_provider"] == "mock"
    assert health["is_mock"] is True
    assert health["fallback_active"] is True
