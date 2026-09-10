import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.prompt_run_log import PromptRunLog
from app.models.prompt_template import PromptTemplate
from app.schemas.llm import LLMStructuredResult, LLMUsage
from app.schemas.content_draft_v2 import DraftGenerateV2Result
from app.services.content_draft_v2_sev import ContentDraftV2Service
from app.main import app

client = TestClient(app)


def fake_draft_v2_result() -> DraftGenerateV2Result:
    return DraftGenerateV2Result.model_validate(
        {
            "title_candidates": [
                "Real LLM title one",
                "Real LLM title two",
                "Real LLM title three",
            ],
            "recommended_title": "Real LLM title one",
            "cover_text": "Real LLM cover",
            "cover_subtitle": "Real LLM subtitle",
            "body_text": "Real LLM generated body with concrete project advice.",
            "image_script": [
                {"index": 1, "title": "Problem", "content": "Explain the learner pain point.", "visual_hint": "Cover"},
                {"index": 2, "title": "Path", "content": "Show the implementation path.", "visual_hint": "Flow"},
                {"index": 3, "title": "Proof", "content": "Connect evidence to the draft.", "visual_hint": "Evidence list"},
                {"index": 4, "title": "Next", "content": "Close with a practical next step.", "visual_hint": "Checklist"},
            ],
            "tag_list": ["AI Agent", "project"],
            "keyword_list": ["content draft", "real llm"],
            "cta_text": "Save this and compare it with your project plan.",
        }
    )


class FakeDraftV2LLMClient:
    def generate_structured_with_context(self, *args, **kwargs) -> LLMStructuredResult:
        data = fake_draft_v2_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=11, completion_tokens=22, total_tokens=33),
            estimated_cost=0,
            raw_response_id="fake-real-draft-v2-response",
            is_mock=False,
        )


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
    create_manual_competitor_data(account_id)

    report_response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "Draft V2 upstream report", "keyword": "AI Agent"},
    )
    assert report_response.status_code == 200
    return report_response.json()["data"]["id"]


def create_manual_competitor_data(account_id: int) -> None:
    """Create non-mock competitor data for V2 report tests."""
    with SessionLocal() as db:
        competitor_account = CompetitorAccount(
            account_id=account_id,
            platform_account_id=f"manual-draft-account-{account_id}",
            nickname="AI Agent 项目学姐",
            homepage_url="https://www.xiaohongshu.com/user/profile/manual-draft-agent",
            bio="专注分享 AI Agent 学习路线、项目实战和求职经验。",
            follower_count=18000,
            note_count=96,
            source_type="MANUAL",
            provider_name="manual_snapshot",
            is_mock=False,
            confidence=0.9,
            raw_snapshot={"source": "manual_test_fixture"},
        )
        db.add(competitor_account)
        db.flush()

        notes = [
            CompetitorNote(
                account_id=account_id,
                competitor_account_id=competitor_account.id,
                note_id=f"manual-draft-note-{account_id}-001",
                note_url="https://www.xiaohongshu.com/explore/manual-draft-agent-001",
                author_name="AI求职经验分享",
                title="双非本科怎么做一个能写进简历的 Agent 项目",
                content="围绕普通本科生如何从后端项目转向 Agent 应用开发，拆解项目选题、技术栈、简历表达和面试准备。",
                tags=["AI Agent", "双非求职", "简历项目", "Python"],
                like_count=128,
                collect_count=96,
                comment_count=18,
                source_type="MANUAL",
                provider_name="manual_snapshot",
                is_mock=False,
                confidence=0.9,
                raw_snapshot={"source": "manual_test_fixture"},
            ),
            CompetitorNote(
                account_id=account_id,
                competitor_account_id=competitor_account.id,
                note_id=f"manual-draft-note-{account_id}-002",
                note_url="https://www.xiaohongshu.com/explore/manual-draft-agent-002",
                author_name="AI Agent 项目学姐",
                title="AI Agent 学习路线：从 API 调用到业务闭环",
                content="拆解普通学生可落地的 AI Agent 项目路径，包含需求分析、工具调用、记忆模块和效果复盘。",
                tags=["AI Agent", "学习路线", "项目实战", "后端开发"],
                like_count=168,
                collect_count=118,
                comment_count=25,
                source_type="MANUAL",
                provider_name="manual_snapshot",
                is_mock=False,
                confidence=0.9,
                raw_snapshot={"source": "manual_test_fixture"},
            ),
            CompetitorNote(
                account_id=account_id,
                competitor_account_id=competitor_account.id,
                note_id=f"manual-draft-note-{account_id}-003",
                note_url="https://www.xiaohongshu.com/explore/manual-draft-agent-003",
                author_name="AI Agent 项目学姐",
                title="能写进简历的 AI Agent 项目应该长什么样",
                content="用小红书内容运营场景说明 Agent 工作流设计、评估指标、人工确认和转化复盘。",
                tags=["AI Agent", "简历项目", "求职项目", "Python"],
                like_count=196,
                collect_count=132,
                comment_count=31,
                source_type="MANUAL",
                provider_name="manual_snapshot",
                is_mock=False,
                confidence=0.9,
                raw_snapshot={"source": "manual_test_fixture"},
            ),
        ]
        db.add_all(notes)
        db.flush()
        db.add_all(
            [
                CompetitorComment(
                    account_id=account_id,
                    competitor_note_id=notes[0].id,
                    comment_id=f"manual-draft-comment-{account_id}-001",
                    user_name="普通本科生",
                    content="双非没有实习，做 Agent 项目真的有用吗？",
                    like_count=12,
                    source_type="MANUAL",
                    provider_name="manual_snapshot",
                    is_mock=False,
                    confidence=0.9,
                    raw_snapshot={"source": "manual_test_fixture"},
                ),
                CompetitorComment(
                    account_id=account_id,
                    competitor_note_id=notes[1].id,
                    comment_id=f"manual-draft-comment-{account_id}-002",
                    user_name="27届学生",
                    content="想知道这种项目怎么写到简历里，面试官会不会觉得是套壳？",
                    like_count=8,
                    source_type="MANUAL",
                    provider_name="manual_snapshot",
                    is_mock=False,
                    confidence=0.9,
                    raw_snapshot={"source": "manual_test_fixture"},
                ),
                CompetitorComment(
                    account_id=account_id,
                    competitor_note_id=notes[2].id,
                    comment_id=f"manual-draft-comment-{account_id}-003",
                    user_name="转码新手",
                    content="想看完整项目结构和源码，尤其是工具调用和复盘模块怎么拆。",
                    like_count=10,
                    source_type="MANUAL",
                    provider_name="manual_snapshot",
                    is_mock=False,
                    confidence=0.9,
                    raw_snapshot={"source": "manual_test_fixture"},
                ),
            ]
        )
        db.commit()


def create_experiment(account_id: int) -> int:
    """Create a candidate content experiment."""
    report_id = create_report(account_id)
    response = client.post(
        "/api/experiments/generate",
        json={"account_id": account_id, "report_id": report_id, "limit": 3},
    )
    assert response.status_code == 200
    return response.json()["data"]["experiments"][0]["id"]


def test_llm_client_requires_real_config_without_api_key(monkeypatch):
    """Ensure the default no-key path does not implicitly use MockLLMClient."""
    monkeypatch.setattr("app.llm.client.settings.llm_api_key", None)

    with pytest.raises(LLMError, match="LLM_CONFIG_MISSING"):
        LLMClient().generate_structured("generate a draft", DraftGenerateV2Result)


def test_generate_draft_requires_approved_experiment():
    """Ensure candidate experiments cannot generate drafts."""
    account_id = create_account()
    experiment_id = create_experiment(account_id)

    response = client.post("/api/drafts/generate", json={"experiment_id": experiment_id})

    assert response.status_code == 400
    assert "APPROVED" in response.json()["message"]


def test_generate_regenerate_and_version_draft(monkeypatch):
    """Generate a draft, regenerate title fields, and create a manual version."""
    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", FakeDraftV2LLMClient)
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
    assert draft["raw_response_id"] == "fake-real-draft-v2-response"
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
        latest_log = (
            db.query(PromptRunLog)
            .filter(PromptRunLog.prompt_name == "xhs_draft_generation")
            .order_by(PromptRunLog.id.desc())
            .first()
        )
        assert latest_log.provider == "qwen"
        assert latest_log.is_mock is False

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
