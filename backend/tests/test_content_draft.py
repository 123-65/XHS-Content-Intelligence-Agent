from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.errors import LLMError, LLMOutputParseError, LLMSchemaValidationError
from app.main import app
from app.models.content_draft import ContentDraft
from app.schemas.content_draft import DraftGenerateResult, ImageScript
from app.schemas.llm import LLMStructuredResult, LLMUsage
from app.schemas.provider_status import ProviderErrorCode

client = TestClient(app)


def count_drafts(experiment_id: int) -> int:
    with SessionLocal() as db:
        return db.query(ContentDraft).filter(ContentDraft.experiment_id == experiment_id).count()


def fake_draft_result() -> DraftGenerateResult:
    return DraftGenerateResult(
        title="Real LLM draft title",
        body="Real LLM generated body with practical and concrete advice.",
        tags=["AI Agent", "draft"],
        cover_text="Real LLM cover",
        image_scripts=[
            ImageScript(index=1, title="Start", content="Explain the problem.", visual_hint="Clean cover"),
            ImageScript(index=2, title="Path", content="Show the learning path.", visual_hint="Flow"),
            ImageScript(index=3, title="Project", content="Show the project loop.", visual_hint="Checklist"),
            ImageScript(index=4, title="Result", content="Summarize the output.", visual_hint="Table"),
        ],
        cta="Save this draft and compare it with your current project.",
    )


class FakeDraftLLMClient:
    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        data = fake_draft_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0,
            raw_response_id="fake-real-draft-response",
            is_mock=False,
        )


class FailingDraftLLMClient:
    def __init__(self, exc: LLMError):
        self.exc = exc

    def generate_structured(self, *args, **kwargs):
        raise self.exc


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/accounts",
        json={
            "account_name": "草稿测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/draft-test",
            "positioning": "帮助大学生学习 AI Agent 项目",
            "target_audience": "大学生、转码初学者、27届应届生",
            "business_model": "资料包 / 咨询",
            "main_product": "AI Agent 项目资料包",
            "lead_value": 15,
            "avg_order_value": 99,
            "gross_profit": 80,
            "primary_goal": "lead",
            "tone_preference": "通俗直接",
            "forbidden_topics": "不夸大收益",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_test_experiment() -> int:
    """创建测试内容实验并返回实验 ID。"""
    account_id = create_test_account()
    response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "experiment_name": "AI Agent 学习路线内容实验",
            "hypothesis": "路线型内容更容易带来收藏和评论。",
            "target_metric": "collect",
            "expected_result": "收藏数 >= 100",
            "topic_angle": "路线步骤型",
            "selected_topic": "普通大学生 AI Agent 学习路线",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_generate_content_draft_with_mock():
    """测试使用 mock 生成内容草稿。"""
    experiment_id = create_test_experiment()

    response = client.post(
        "/drafts/generate",
        json={
            "experiment_id": experiment_id,
            "user_requirement": "语气像学姐给普通大学生的实话建议，不要太营销",
            "use_mock": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["experiment_id"] == experiment_id
    assert data["image_scripts"]
    assert data["version"] == 1
    assert data["status"] == "GENERATED"


def test_generate_content_draft_default_uses_real_llm_schema(monkeypatch):
    experiment_id = create_test_experiment()
    monkeypatch.setattr("app.services.content_draft_sev.LLMClient", FakeDraftLLMClient)

    response = client.post(
        "/drafts/generate",
        json={"experiment_id": experiment_id, "user_requirement": "Use the real structured LLM path."},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Real LLM draft title"
    assert data["raw_response_id"] == "fake-real-draft-response"
    assert data["total_tokens"] == 30
    assert count_drafts(experiment_id) == 1


def test_generate_content_draft_default_llm_config_missing_does_not_create_draft(monkeypatch):
    experiment_id = create_test_experiment()
    monkeypatch.setattr(
        "app.services.content_draft_sev.LLMClient",
        lambda: FailingDraftLLMClient(LLMError(f"{ProviderErrorCode.LLM_CONFIG_MISSING.value}: missing api key")),
    )

    response = client.post("/drafts/generate", json={"experiment_id": experiment_id})

    assert response.status_code == 500
    assert ProviderErrorCode.LLM_CONFIG_MISSING.value in response.json()["message"]
    assert count_drafts(experiment_id) == 0


def test_generate_content_draft_invalid_json_does_not_create_draft(monkeypatch):
    experiment_id = create_test_experiment()
    monkeypatch.setattr(
        "app.services.content_draft_sev.LLMClient",
        lambda: FailingDraftLLMClient(
            LLMOutputParseError(f"{ProviderErrorCode.LLM_OUTPUT_PARSE_FAILED.value}: LLM output is not valid JSON")
        ),
    )

    response = client.post("/drafts/generate", json={"experiment_id": experiment_id})

    assert response.status_code == 500
    assert ProviderErrorCode.LLM_OUTPUT_PARSE_FAILED.value in response.json()["message"]
    assert count_drafts(experiment_id) == 0


def test_generate_content_draft_schema_invalid_does_not_create_draft(monkeypatch):
    experiment_id = create_test_experiment()
    monkeypatch.setattr(
        "app.services.content_draft_sev.LLMClient",
        lambda: FailingDraftLLMClient(
            LLMSchemaValidationError(f"{ProviderErrorCode.LLM_SCHEMA_INVALID.value}: LLM output does not match target schema")
        ),
    )

    response = client.post("/drafts/generate", json={"experiment_id": experiment_id})

    assert response.status_code == 500
    assert ProviderErrorCode.LLM_SCHEMA_INVALID.value in response.json()["message"]
    assert count_drafts(experiment_id) == 0


def test_list_and_get_content_draft():
    """测试查询实验草稿列表和草稿详情。"""
    experiment_id = create_test_experiment()
    create_response = client.post("/drafts/generate", json={"experiment_id": experiment_id, "use_mock": True})
    draft_id = create_response.json()["data"]["id"]

    list_response = client.get(f"/drafts/experiment/{experiment_id}")
    assert list_response.status_code == 200
    assert any(item["id"] == draft_id for item in list_response.json()["data"])

    detail_response = client.get(f"/drafts/{draft_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == draft_id
