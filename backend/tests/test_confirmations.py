from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment

client = TestClient(app)


def create_account() -> int:
    """Create a minimal account profile."""
    with SessionLocal() as db:
        account = AccountProfile(
            account_name=f"confirmation-account-{uuid4().hex[:8]}",
            platform="xhs",
            homepage_url="https://www.xiaohongshu.com/user/profile/confirmation-test",
            content_domain="AI Agent",
            positioning="Practical AI Agent project account",
            target_audience="Students and junior developers",
            persona="Project mentor",
            monetization_goal="Resource pack",
            business_model="Resource pack",
            main_product="AI Agent project pack",
            lead_value=10,
            avg_order_value=99,
            gross_profit=80,
            primary_goal="lead",
            tone_preference="Clear",
            forbidden_topics="No unsafe promises",
            risk_preference="BALANCED",
            account_stage="STARTUP",
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def create_experiment(account_id: int, risk_level: str = "LOW") -> int:
    """Create a minimal content experiment."""
    with SessionLocal() as db:
        experiment = ContentExperiment(
            account_id=account_id,
            experiment_name=f"confirmation-experiment-{uuid4().hex[:8]}",
            hypothesis="If the angle is clearer, saves may improve.",
            content_pillar="PROJECT",
            content_format="image note",
            main_variable="title_angle",
            control_variables=[{"name": "cta_strength", "value": "SOFT"}],
            primary_metric="collect",
            secondary_metrics=["comment", "lead"],
            success_criteria={"primary_metric": "collect", "target_values": {"collect_count": 60}},
            failure_criteria={"primary_metric": "collect", "target_values": {"collect_count": 36}},
            fallback_strategy="Change the title angle and retest.",
            risk_level=risk_level,
            target_metric="collect",
            expected_result="collect_count >= 60",
            topic_angle="Beginner AI Agent path",
            selected_topic="AI Agent project path",
            target_values={"collect_count": 60},
            source_type="CONTENT_OPPORTUNITY",
            status="CANDIDATE",
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        return experiment.id


def create_draft(account_id: int) -> int:
    """Create a minimal content draft linked to an experiment."""
    experiment_id = create_experiment(account_id, "LOW")
    with SessionLocal() as db:
        draft = ContentDraft(
            experiment_id=experiment_id,
            title="AI Agent project path",
            body="Draft body",
            tags=["AI Agent"],
            cover_text="Project path",
            image_scripts=[{"index": 1, "content": "Start"}],
            cta="Save this checklist.",
            title_candidates=["AI Agent project path", "Build a useful Agent", "Project loop first"],
            recommended_title="AI Agent project path",
            cover_subtitle="Business loop first",
            body_text="Draft body",
            image_script=[{"index": 1, "content": "Start"}],
            tag_list=["AI Agent"],
            keyword_list=["content experiment"],
            cta_text="Save this checklist.",
            version=1,
            status="GENERATED",
            generation_context={},
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft.id


def test_create_pending_and_approve_experiment_confirmation():
    """Test experiment confirmation creation, listing, decision, and audit logs."""
    account_id = create_account()
    experiment_id = create_experiment(account_id)

    create_response = client.post(
        "/api/confirmations",
        json={"confirmation_type": "EXPERIMENT_CONFIRM", "target_id": experiment_id, "created_by": "operator"},
    )

    assert create_response.status_code == 200
    task = create_response.json()["data"]
    task_id = task["id"]
    assert task["account_id"] == account_id
    assert task["status"] == "PENDING"
    assert task["summary"].startswith("Confirm experiment")
    assert task["recommendation"]
    assert task["risk_level"] == "LOW"
    assert len(task["audit_logs"]) == 1
    assert task["audit_logs"][0]["event_type"] == "CREATED"

    pending_response = client.get(f"/api/confirmations/pending?account_id={account_id}")
    assert pending_response.status_code == 200
    assert any(item["id"] == task_id for item in pending_response.json()["data"]["tasks"])

    decision_response = client.post(
        f"/api/confirmations/{task_id}/decision",
        json={"decision": "APPROVED", "decided_by": "human-reviewer", "comment": "Looks good."},
    )

    assert decision_response.status_code == 200
    decided = decision_response.json()["data"]
    assert decided["status"] == "APPROVED"
    assert decided["decisions"][0]["decision"] == "APPROVED"
    assert len(decided["audit_logs"]) == 2
    assert decided["audit_logs"][-1]["event_type"] == "DECISION_SUBMITTED"

    with SessionLocal() as db:
        assert db.get(ContentExperiment, experiment_id).status == "APPROVED"


def test_high_risk_confirmation_cannot_be_ignored():
    """Test that high-risk tasks cannot be paused or cancelled directly."""
    account_id = create_account()
    create_response = client.post(
        "/api/confirmations",
        json={
            "confirmation_type": "HIGH_RISK_CONFIRM",
            "target_id": 9001,
            "account_id": account_id,
            "created_by": "system",
            "extra_context": {"reason": "unsafe action requires human review"},
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]
    assert create_response.json()["data"]["risk_level"] == "HIGH"

    ignored_response = client.post(
        f"/api/confirmations/{task_id}/decision",
        json={"decision": "CANCELLED", "decided_by": "human-reviewer", "comment": "ignore it"},
    )
    assert ignored_response.status_code == 400

    rejected_response = client.post(
        f"/api/confirmations/{task_id}/decision",
        json={"decision": "REJECTED", "decided_by": "human-reviewer", "comment": "Risk rejected."},
    )
    assert rejected_response.status_code == 200
    assert rejected_response.json()["data"]["status"] == "REJECTED"


def test_publish_confirmation_invalidates_when_draft_version_changes():
    """Test stale publish confirmations are invalidated after draft version changes."""
    account_id = create_account()
    draft_id = create_draft(account_id)
    create_response = client.post(
        "/api/confirmations",
        json={"confirmation_type": "PUBLISH_CONFIRM", "target_id": draft_id, "created_by": "operator"},
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]
    assert create_response.json()["data"]["target_version"] == 1

    with SessionLocal() as db:
        draft = db.get(ContentDraft, draft_id)
        draft.version = 2
        db.commit()

    detail_response = client.get(f"/api/confirmations/{task_id}")

    assert detail_response.status_code == 200
    task = detail_response.json()["data"]
    assert task["status"] == "INVALIDATED"
    assert task["invalidated_reason"] == "draft version changed"
    assert any(log["event_type"] == "INVALIDATED" for log in task["audit_logs"])

    decision_response = client.post(
        f"/api/confirmations/{task_id}/decision",
        json={"decision": "APPROVED", "decided_by": "human-reviewer"},
    )
    assert decision_response.status_code == 400
