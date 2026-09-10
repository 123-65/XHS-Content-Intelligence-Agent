import pytest

from app.llm.client import LLMClient
from app.llm.errors import LLMError, LLMResponseError
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.router import configured_provider_name, llm_health
from app.schemas.llm import LLMResult, LLMStructuredResult, LLMUsage
from app.schemas.llm_test import LLMTestAnalysisResult
from app.schemas.provider_status import ProviderErrorCode


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


def test_default_provider_name_is_not_mock(monkeypatch):
    """测试未配置默认 Provider 时不会回到 mock。"""
    monkeypatch.setattr("app.llm.router.settings.llm_provider", "")

    assert configured_provider_name(None) == "deepseek"
    assert configured_provider_name(None) != "mock"



def test_no_api_key_does_not_fall_back_to_mock(monkeypatch):
    """测试无真实配置时不会隐式回退 Mock。"""
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "qwen")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: MockLLMProvider())
    with pytest.raises(LLMError, match="implicit fallback"):
        LLMClient()


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


def test_provider_failure_raises_without_mock_fallback(monkeypatch):
    """测试真实 Provider 调用失败时抛错，不自动回退 Mock。"""
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "deepseek")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: FakeFailingProvider())

    with pytest.raises(LLMError, match="upstream timeout"):
        LLMClient().generate_text("test prompt")


def test_generate_structured_parses_real_provider_json(monkeypatch):
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "qwen")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: FakeRealProvider())

    result = LLMClient().generate_structured("structured prompt", LLMTestAnalysisResult)

    assert isinstance(result.data, LLMTestAnalysisResult)
    assert result.data.summary == "real structured result"
    assert result.data.score == 88
    assert result.provider == "qwen"


def test_provider_health_reports_missing_config_without_mock_fallback(monkeypatch):
    """测试 LLM 健康检查在缺少配置时返回不可用状态，不启用 Mock fallback。"""
    monkeypatch.setattr("app.llm.router.settings.llm_provider", "qwen")
    monkeypatch.setattr("app.llm.router.settings.llm_api_key", None)

    health = llm_health()

    assert health["requested_provider"] == "qwen"
    assert health["active_provider"] is None
    assert health["available"] is False
    assert health["is_mock"] is False
    assert health["fallback_provider"] is None
    assert health["fallback_active"] is False
    assert health["error_code"] == ProviderErrorCode.LLM_CONFIG_MISSING.value


def test_llm_health_returns_expected_fields(monkeypatch):
    """测试 LLM health 返回配置诊断字段。"""
    monkeypatch.setattr("app.llm.router.settings.llm_provider", "qwen")
    monkeypatch.setattr("app.llm.router.settings.llm_api_key", None)
    monkeypatch.setattr("app.llm.router.settings.llm_base_url", "https://example.test/v1")
    monkeypatch.setattr("app.llm.router.settings.llm_model", "qwen-plus")

    health = llm_health()

    expected_fields = {
        "requested_provider",
        "available",
        "configured",
        "base_url_configured",
        "api_key_configured",
        "model_configured",
        "fallback_active",
        "error_code",
        "provider_candidates",
        "production_provider_candidates",
    }
    assert expected_fields <= set(health)
    assert health["fallback_active"] is False
    assert health["fallback_provider"] is None
    assert "mock" not in health["production_provider_candidates"]


def test_unsupported_provider_raises_provider_unavailable():
    """测试不支持的 provider 返回统一错误码。"""
    with pytest.raises(LLMError, match=ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value):
        LLMClient(provider_name="unknown_provider")


def test_llm_provider_error_code_enums_keep_expected_values():
    """测试 LLM Provider 错误码枚举值保持稳定。"""
    assert ProviderErrorCode.LLM_CONFIG_MISSING.value == "LLM_CONFIG_MISSING"
    assert ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value == "LLM_PROVIDER_UNAVAILABLE"


def test_explicit_mock_provider_is_allowed():
    """测试显式指定 mock provider 时允许使用 MockLLM。"""
    client = LLMClient(provider_name="mock")
    result = client.generate_text("test prompt", prompt_key="unit_test", prompt_version="v1")

    assert result.provider == "mock"
    assert result.is_mock is True
    assert result.fallback_used is False
    assert result.fallback_from is None
    assert result.prompt_key == "unit_test"
    assert result.prompt_version == "v1"
    assert result.latency_ms >= 0
