from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.client import LLMClient
from app.models.prompt_run_log import PromptRunLog
from app.models.prompt_template import PromptTemplate
from app.schemas.content_draft_v2 import DraftGenerateV2Result
from app.services.content_draft_v2_sev import ContentDraftV2Service
from app.main import app

client = TestClient(app)


def create_account() -> int:
    """Create an account profile for draft tests."""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": "Draft V2 Test Account",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/draft-v2-test",
            "content_domain": "AI Agent",
            "positioning": "Help students build practical AI Agent projects",
            "target_audience": "Students and junior developers",
            "persona": "Practical project mentor",
            "monetization_goal": "Resource pack and consulting",
            "business_model": "Resource pack",
            "main_product": "AI Agent project pack",
            "lead_value": 15,
            "avg_order_value": 99,
            "gross_profit": 80,
            "primary_goal": "lead",
            "tone_preference": "Clear and practical",
            "forbidden_topics": "No exaggerated income claims",
            "account_stage": "STARTUP",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_report(account_id: int) -> int:
    """Create competitor data and return an analysis report ID."""
    task_response = client.post(
        "/api/crawler/tasks",
        json={
            "account_id": account_id,
            "task_type": "COMPETITOR_SEED",
            "provider_name": "seed_sample",
            "keyword": "AI Agent",
        },
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["data"]["id"]
    assert client.post(f"/api/crawler/tasks/{task_id}/run").status_code == 200

    report_response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "Draft V2 upstream report", "keyword": "AI Agent"},
    )
    assert report_response.status_code == 200
    return report_response.json()["data"]["id"]


def create_experiment(account_id: int) -> int:
    """Create a candidate content experiment."""
    report_id = create_report(account_id)
    response = client.post(
        "/api/experiments/generate",
        json={"account_id": account_id, "report_id": report_id, "limit": 3},
    )
    assert response.status_code == 200
    return response.json()["data"]["experiments"][0]["id"]


def test_llm_client_uses_mock_without_api_key(monkeypatch):
    """Ensure the default no-key path uses MockLLMClient."""
    monkeypatch.setattr("app.llm.client.settings.llm_api_key", None)

    result = LLMClient().generate_structured("generate a draft", DraftGenerateV2Result)

    assert result.provider.startswith("mock-")
    assert result.model.startswith("mock-")
    assert result.data.recommended_title in result.data.title_candidates
    assert len(result.data.image_script) >= 4


def test_generate_draft_requires_approved_experiment():
    """Ensure candidate experiments cannot generate drafts."""
    account_id = create_account()
    experiment_id = create_experiment(account_id)

    response = client.post("/api/drafts/generate", json={"experiment_id": experiment_id})

    assert response.status_code == 400
    assert "APPROVED" in response.json()["message"]


def test_generate_regenerate_and_version_draft(monkeypatch):
    """Generate a draft, regenerate title fields, and create a manual version."""
    monkeypatch.setattr("app.llm.client.settings.llm_api_key", None)
    account_id = create_account()
    experiment_id = create_experiment(account_id)
    approve_response = client.post(f"/api/experiments/{experiment_id}/approve")
    assert approve_response.status_code == 200

    generate_response = client.post(
        "/api/drafts/generate",
        json={"experiment_id": experiment_id, "user_requirement": "Keep the draft practical and concise."},
    )

    assert generate_response.status_code == 200
    draft = generate_response.json()["data"]
    draft_id = draft["id"]
    assert draft["recommended_title"] in draft["title_candidates"]
    assert draft["cover_text"]
    assert draft["cover_subtitle"]
    assert draft["body_text"]
    assert len(draft["image_script"]) >= 4
    assert draft["tag_list"]
    assert draft["keyword_list"]
    assert draft["cta_text"]
    assert draft["generation_context_record"]["account_id"] == account_id
    assert draft["generation_context_record"]["experiment_id"] == experiment_id
    assert draft["versions"][0]["regenerate_scope"] == "all"

    with SessionLocal() as db:
        template = (
            db.query(PromptTemplate)
            .filter(PromptTemplate.prompt_name == "xhs_draft_generation", PromptTemplate.prompt_version == "v2.0")
            .one_or_none()
        )
        assert template is not None
        assert template.template_path == "backend/app/prompts/xhs_draft_v2.py"
        log_count = db.query(PromptRunLog).filter(PromptRunLog.prompt_name == "xhs_draft_generation").count()
        assert log_count >= 1

    regenerate_response = client.post(
        f"/api/drafts/{draft_id}/regenerate",
        json={"scope": "title", "user_requirement": "Make the title sharper."},
    )
    assert regenerate_response.status_code == 200
    regenerated = regenerate_response.json()["data"]
    assert regenerated["version"] == 2
    assert regenerated["body_text"] == draft["body_text"]
    assert regenerated["versions"][0]["regenerate_scope"] == "title"

    version_response = client.post(f"/api/drafts/{draft_id}/versions", json={"note": "manual snapshot"})
    assert version_response.status_code == 200
    assert version_response.json()["data"]["regenerate_scope"] == "manual_snapshot"

    detail_response = client.get(f"/api/drafts/{draft_id}")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["data"]["versions"]) >= 3


def test_baseline_risk_check_blocks_prohibited_phrases():
    """Ensure prohibited draft phrases are rejected before persistence."""
    unsafe = DraftGenerateV2Result.model_validate(
        {
            "title_candidates": ["safe title one", "safe title two", "safe title three"],
            "recommended_title": "safe title one",
            "cover_text": "safe cover",
            "cover_subtitle": "safe subtitle",
            "body_text": "\u4fdd\u8bc1\u6da8\u7c89",
            "image_script": [
                {"index": 1, "title": "a", "content": "safe", "visual_hint": "safe"},
                {"index": 2, "title": "b", "content": "safe", "visual_hint": "safe"},
                {"index": 3, "title": "c", "content": "safe", "visual_hint": "safe"},
                {"index": 4, "title": "d", "content": "safe", "visual_hint": "safe"},
            ],
            "tag_list": ["AI Agent"],
            "keyword_list": ["content experiment"],
            "cta_text": "safe CTA",
        }
    )

    try:
        ContentDraftV2Service.__new__(ContentDraftV2Service)._ensure_risk_safe(unsafe)
    except ValueError as exc:
        assert "\u4e0d\u5141\u8bb8\u4fdd\u8bc1\u6da8\u7c89" in str(exc)
    else:
        raise AssertionError("risk check should reject prohibited phrases")
