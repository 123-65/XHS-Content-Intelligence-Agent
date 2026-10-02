import json
import ast
import inspect
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.llm.client import LLMClient
from app.llm.errors import LLMResponseError, LLMSchemaValidationError
from app.llm.providers.base import OpenAICompatibleProvider
from app.llm.providers.qwen_provider import QwenProvider
from app.services.content_strategy_sev import ContentStrategyService
from app.services.draft_generation_sev import DraftGenerationService
from app.services.draft_review_sev import DraftReviewService
from app.services.draft_revision_sev import DraftRevisionService


class Contract(BaseModel):
    name: str
    score: int = Field(ge=1)


class Recorder:
    def __init__(self):
        self.items = []

    def record(self, evidence):
        self.items.append(evidence)


class Completions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        self.requests = []

    def create(self, **kwargs):
        self.calls += 1
        self.requests.append(kwargs)
        value = self.outputs.pop(0)
        if isinstance(value, Exception):
            raise value
        return SimpleNamespace(
            id="response-id",
            choices=[SimpleNamespace(message=SimpleNamespace(content=value))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


def client(monkeypatch, outputs, recorder):
    provider = OpenAICompatibleProvider(api_key="configured", base_url="https://example.test/v1", model="test-model")
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions(outputs)))
    monkeypatch.setattr("app.llm.client.configured_provider_name", lambda provider_name=None: "qwen")
    monkeypatch.setattr("app.llm.client.build_llm_provider", lambda provider_name=None: provider)
    return LLMClient(evidence_recorder=recorder)


def provider_calls(llm):
    return llm.provider_impl.client.chat.completions.calls


def test_qwen_provider_disables_sdk_internal_retries(monkeypatch):
    captured = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr("app.llm.providers.base.OpenAI", fake_openai)

    QwenProvider(api_key="configured", base_url="https://example.test/v1", model="test-model")

    assert captured["max_retries"] == 0
    assert captured["timeout"] == 30


def test_research_analysis_timeout_has_finite_default_and_rejects_non_positive():
    research = Settings(_env_file=None)
    assert research.llm_research_analysis_model == "qwen3.7-flash-2026-07-15"
    assert research.llm_research_analysis_timeout_seconds == 120
    assert research.llm_research_analysis_enable_thinking is False
    with pytest.raises(ValueError, match="LLM_RESEARCH_ANALYSIS_TIMEOUT_SECONDS"):
        Settings(_env_file=None, llm_research_analysis_timeout_seconds=0)


def test_post_publish_review_policy_defaults_to_global_fallback_and_rejects_non_positive_timeout():
    review = Settings(
        _env_file=None,
        llm_post_publish_review_model=None,
        llm_post_publish_review_timeout_seconds=None,
        llm_post_publish_review_enable_thinking=None,
    )
    assert review.llm_post_publish_review_model is None
    assert review.llm_post_publish_review_timeout_seconds is None
    assert review.llm_post_publish_review_enable_thinking is None
    with pytest.raises(ValueError, match="LLM_POST_PUBLISH_REVIEW_TIMEOUT_SECONDS"):
        Settings(_env_file=None, llm_post_publish_review_timeout_seconds=0)


def test_draft_revision_policy_defaults_to_global_fallback_and_rejects_non_positive_timeout():
    revision = Settings(
        _env_file=None,
        llm_draft_revision_model=None,
        llm_draft_revision_timeout_seconds=None,
        llm_draft_revision_enable_thinking=None,
    )
    assert revision.llm_draft_revision_model is None
    assert revision.llm_draft_revision_timeout_seconds is None
    assert revision.llm_draft_revision_enable_thinking is None
    with pytest.raises(ValueError, match="LLM_DRAFT_REVISION_TIMEOUT_SECONDS"):
        Settings(_env_file=None, llm_draft_revision_timeout_seconds=0)


def test_provider_json_mode_carries_complete_draft_revision_schema_in_prompt():
    from app.schemas.draft import DraftRevisionLLMResult

    provider = OpenAICompatibleProvider(api_key=None, base_url=None, model="test")
    prompt = provider._json_prompt("revise", DraftRevisionLLMResult.model_json_schema())

    assert '"applied_changes"' in prompt
    assert '"required"' in prompt
    assert "Fill every required field" in prompt


def test_one_provider_failure_is_one_http_call_per_adapter_attempt(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, [RuntimeError("unavailable"), '{"name":"x","score":2}'], recorder)

    result = llm.generate_structured("prompt", Contract)

    assert result.data.score == 2
    assert provider_calls(llm) == 2
    assert [item["attempt_status"] for item in recorder.items] == ["PROVIDER_FAILED", "SUCCESS"]


def test_adapter_timeout_is_not_retried_beyond_business_deadline(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, [TimeoutError("timeout-1")], recorder)

    with pytest.raises(LLMResponseError):
        llm.generate_structured("prompt", Contract)

    assert provider_calls(llm) == 1
    assert [item["attempt_number"] for item in recorder.items] == [1]
    assert [item["attempt_status"] for item in recorder.items] == ["PROVIDER_FAILED"]


def test_first_adapter_success_makes_one_http_call(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"x","score":2}'], recorder)

    result = llm.generate_structured("prompt", Contract)

    assert result.data.score == 2
    assert provider_calls(llm) == 1
    assert [item["attempt_status"] for item in recorder.items] == ["SUCCESS"]


def test_model_override_is_sent_to_provider_and_observability(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"x","score":2}'], recorder)

    result = llm.generate_structured("prompt", Contract, model="fast-semantic-model")

    assert result.model == "fast-semantic-model"
    assert recorder.items[0]["model"] == "fast-semantic-model"


def test_per_call_thinking_override_is_only_forwarded_when_requested(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"x","score":2}', '{"name":"y","score":2}'], recorder)

    llm.generate_structured(
        "prompt", Contract, model="fast-semantic-model",
        extra_body={"enable_thinking": False},
    )
    llm.generate_structured("prompt", Contract)

    requests = llm.provider_impl.client.chat.completions.requests
    assert requests[0]["extra_body"] == {"enable_thinking": False}
    assert "extra_body" not in requests[1]


def test_per_call_timeout_override_is_only_forwarded_when_requested(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"x","score":2}', '{"name":"y","score":2}'], recorder)

    llm.generate_structured("prompt", Contract, timeout_seconds=120)
    llm.generate_structured("prompt", Contract)

    requests = llm.provider_impl.client.chat.completions.requests
    assert requests[0]["timeout"] == 120
    assert "timeout" not in requests[1]


def test_content_generation_services_keep_default_model_and_use_only_bounded_timeout_override():
    services = (ContentStrategyService, DraftGenerationService, DraftReviewService, DraftRevisionService)

    for service in services:
        tree = ast.parse(inspect.getsource(service))
        structured_calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "generate_structured"
        ]
        assert structured_calls
        assert all(
            not {"model", "extra_body"}.intersection(keyword.arg for keyword in call.keywords)
            for call in structured_calls
        )
        assert all(
            not (timeout := next((keyword.value for keyword in call.keywords if keyword.arg == "timeout_seconds"), None))
            or (
                isinstance(timeout, ast.Attribute)
                and timeout.attr.startswith("llm_")
                and timeout.attr.endswith("_timeout_seconds")
            )
            for call in structured_calls
        )


def test_first_pydantic_invalid_second_valid_records_both_attempts(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"x","score":0}', '{"name":"x","score":2}'], recorder)

    result = llm.generate_structured("prompt", Contract, prompt_key="contract", prompt_version="v1")

    assert result.data.score == 2
    assert [item["attempt_status"] for item in recorder.items] == ["VALIDATION_FAILED", "SUCCESS"]
    first = recorder.items[0]
    assert first["attempt_number"] == 1 and first["attempt_total"] == 2
    assert first["validation_layer"] == "PYDANTIC_SCHEMA"
    assert first["validation_summary"]["validation_path"] == "score"
    assert first["validation_summary"]["actual_type"] == "int"
    assert first["retry_exhausted"] is False


def test_all_pydantic_attempts_invalid_records_exhaustion(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"x","score":0}', '{"name":"x","score":0}'], recorder)

    with pytest.raises(LLMSchemaValidationError):
        llm.generate_structured("prompt", Contract, prompt_key="contract", prompt_version="v1")

    assert len(recorder.items) == 2
    assert recorder.items[-1]["retry_exhausted"] is True
    assert recorder.items[-1]["final_error_code"] == "LLM_STRUCTURED_VALIDATION_FAILED"


def test_provider_parse_and_provider_failure_are_distinct(monkeypatch):
    parse_recorder = Recorder()
    with pytest.raises(LLMSchemaValidationError):
        client(monkeypatch, ["not-json", "still-not-json"], parse_recorder).generate_structured("prompt", Contract)
    assert {item["validation_layer"] for item in parse_recorder.items} == {"PROVIDER_PARSE"}

    provider_recorder = Recorder()
    with pytest.raises(LLMResponseError):
        client(monkeypatch, [TimeoutError("timeout")], provider_recorder).generate_structured("prompt", Contract)
    assert {item["attempt_status"] for item in provider_recorder.items} == {"PROVIDER_FAILED"}


def test_business_value_error_is_recorded_after_schema_success(monkeypatch):
    output = {
        "strategy_goal": "选题",
        "target_audience": "学生",
        "content_directions": [{"direction": "方向", "rationale": "依据", "evidence_refs": [{"kind": "research_report", "id": 999}]}],
        "rationale": "依据",
        "evidence_refs": [{"kind": "research_report", "id": 999}],
        "applicable_constraints": [],
        "opportunities": [{
            "source_opportunity_id": 3923, "content_goal": "目标", "why_now": "现在",
            "suggested_hook": "开头", "evidence_refs": [{"kind": "research_report", "id": 999}], "constraints": [],
        }],
    }
    recorder = Recorder()
    llm = client(monkeypatch, [json.dumps(output, ensure_ascii=False)], recorder)
    payload = {
        "account_ref": 7, "growth_context": {}, "research_result": {}, "historical_opportunities": [],
        "strategy_memory": [], "evidence_refs": [{"kind": "research_report", "id": 2862}], "constraints": [],
    }

    with pytest.raises(ValueError, match="无效 EvidenceRefs"):
        ContentStrategyService(None, llm_client=llm).generate_semantic(payload)

    assert [item["attempt_status"] for item in recorder.items] == ["SUCCESS", "VALIDATION_FAILED"]
    assert recorder.items[-1]["validation_layer"] == "POST_PARSE_BUSINESS_VALIDATION"
    assert recorder.items[-1]["validation_summary"]["validation_path"] == "evidence_refs.0"
    assert recorder.items[-1]["validation_summary"]["actual_type"] == "dict"
    assert recorder.items[-1]["validation_summary"]["actual_value"]["id"] == 999
    assert recorder.items[-1]["retryable"] is False


def test_business_validation_attempt_metadata_is_recorded_without_raw_candidate(monkeypatch):
    recorder = Recorder()
    llm = client(monkeypatch, ['{"name":"secret raw value","score":2}'], recorder)
    result = llm.generate_structured("prompt", Contract, prompt_key="semantic", prompt_version="v1")
    error = ValueError("mixed goal")
    error.validation_path = "sub_goals"
    error.expected = "workflow intents only"
    error.actual_value = ["QUERY_PROFILE"]

    llm.record_business_validation_failure(
        error,
        result.data,
        attempt_number=1,
        attempt_total=2,
        retry_exhausted=False,
    )

    evidence = recorder.items[-1]
    assert evidence["validation_layer"] == "POST_PARSE_BUSINESS_VALIDATION"
    assert evidence["attempt_number"] == 1
    assert evidence["attempt_total"] == 2
    assert evidence["retryable"] is True
    assert evidence["retry_exhausted"] is False
    assert "secret raw value" not in json.dumps(evidence, ensure_ascii=False)


def test_secrets_and_raw_strings_are_not_retained(monkeypatch):
    secret = "sk-super-secret Authorization: Bearer hidden Cookie=session"
    recorder = Recorder()
    llm = client(monkeypatch, [json.dumps({"name": secret, "score": 0}), json.dumps({"name": secret, "score": 0})], recorder)

    with pytest.raises(LLMSchemaValidationError):
        llm.generate_structured("prompt", Contract, prompt_key="safe", prompt_version="v1")

    serialized = json.dumps(recorder.items, ensure_ascii=False)
    assert "sk-super-secret" not in serialized
    assert "Bearer hidden" not in serialized
    assert "session" not in serialized
