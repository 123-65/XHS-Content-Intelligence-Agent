from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.strategy_memory import StrategyMemory

client = TestClient(app)


def create_account(name_prefix: str = "post-publish-account") -> int:
    """为发布后闭环测试创建账号画像。"""
    with SessionLocal() as db:
        account = AccountProfile(
            account_name=f"{name_prefix}-{uuid4().hex[:8]}",
            platform="xhs",
            homepage_url="https://www.xiaohongshu.com/user/profile/post-publish-test",
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
            tone_preference="Clear and practical",
            forbidden_topics="No exaggerated promises",
            risk_preference="BALANCED",
            account_stage="STARTUP",
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def create_experiment(account_id: int, target_values: dict | None = None) -> int:
    """创建带可衡量收藏目标的内容实验。"""
    with SessionLocal() as db:
        experiment = ContentExperiment(
            account_id=account_id,
            experiment_name=f"post-publish-experiment-{uuid4().hex[:8]}",
            hypothesis="If the project path is concrete, saves should improve.",
            content_pillar="PROJECT",
            content_format="image note",
            main_variable="title_angle",
            control_variables=[{"name": "cta_strength", "value": "SOFT"}],
            primary_metric="collect",
            secondary_metrics=["comment", "lead"],
            success_criteria={"primary_metric": "collect", "target_values": target_values or {"collect_count": 30}},
            failure_criteria={"primary_metric": "collect", "target_values": {"collect_count": 18}},
            fallback_strategy="Change the title angle and retest.",
            risk_level="LOW",
            target_metric="collect",
            expected_result="collect_count >= 30",
            topic_angle="Beginner AI Agent path",
            selected_topic="AI Agent project path",
            target_values=target_values or {"collect_count": 30},
            source_type="CONTENT_OPPORTUNITY",
            status="APPROVED",
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        return experiment.id


def create_draft(experiment_id: int) -> int:
    """创建绑定内容实验的草稿。"""
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
            status="READY_TO_PUBLISH",
            generation_context={},
        )
        db.add(draft)
        db.commit()
        db.refresh(draft)
        return draft.id


def create_publish_chain(target_values: dict | None = None) -> tuple[int, int, int, int]:
    """通过 API 创建账号、实验、草稿和已发布笔记链路。"""
    account_id = create_account()
    experiment_id = create_experiment(account_id, target_values)
    draft_id = create_draft(experiment_id)

    response = client.post(
        "/api/published-notes",
        json={
            "account_id": account_id,
            "experiment_id": experiment_id,
            "draft_id": draft_id,
            "publish_url": f"https://www.xiaohongshu.com/explore/{uuid4().hex}",
            "raw_snapshot": {"submitted_by": "operator"},
        },
    )

    assert response.status_code == 200
    published_note_id = response.json()["data"]["id"]
    return account_id, experiment_id, draft_id, published_note_id


def test_post_publish_feedback_loop_success_path():
    """测试发布、指标回采、复盘、记忆提取和优化应用的成功链路。"""
    account_id, experiment_id, draft_id, published_note_id = create_publish_chain()

    with SessionLocal() as db:
        assert db.get(ContentExperiment, experiment_id).status == "PUBLISHED"
        assert db.get(ContentDraft, draft_id).status == "PUBLISHED"

    collect_response = client.post(
        f"/api/published-notes/{published_note_id}/collect-metrics",
        json={"snapshot_window": "24h", "use_mock": True},
    )
    assert collect_response.status_code == 200
    metrics = collect_response.json()["data"]
    assert metrics["source_type"] == "MOCK"
    assert metrics["collect_count"] == 35

    list_response = client.get(f"/api/published-notes/{published_note_id}/public-metrics")
    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["snapshot_window"] == "24h"

    conversion_response = client.post(
        "/api/conversions/private-snapshots",
        json={
            "published_note_id": published_note_id,
            "snapshot_window": "24h",
            "dm_count": 3,
            "lead_count": 2,
            "wechat_add_count": 1,
            "resource_request_count": 2,
            "deal_count": 1,
            "revenue_amount": "99.00",
            "raw_snapshot": {"source": "manual form"},
        },
    )
    assert conversion_response.status_code == 200
    assert conversion_response.json()["data"]["account_id"] == account_id

    review_response = client.post("/api/reviews", json={"published_note_id": published_note_id})
    assert review_response.status_code == 200
    review = review_response.json()["data"]
    review_id = review["id"]
    assert review["result_status"] == "SUCCESS"
    assert review["data_facts"]
    assert review["inferences"]
    assert review["action_suggestions"]

    memory_response = client.post(f"/api/reviews/{review_id}/memories/extract")
    assert memory_response.status_code == 200
    memory = memory_response.json()["data"]["memories"][0]
    assert memory["status"] == "CANDIDATE"
    assert memory["memory_type"] == "TOPIC_MEMORY"
    assert memory["evidence_count"] >= 3

    list_memory_response = client.get(f"/api/reviews/memories?account_id={account_id}")
    assert list_memory_response.status_code == 200
    assert any(item["id"] == memory["id"] for item in list_memory_response.json()["data"])

    optimization_response = client.post(
        "/api/optimizations/generate",
        json={"account_id": account_id, "review_report_id": review_id},
    )
    assert optimization_response.status_code == 200
    plan = optimization_response.json()["data"]
    assert plan["plan_type"] == "SCALE"
    assert plan["status"] == "CANDIDATE"

    apply_response = client.post(f"/api/optimizations/{plan['id']}/apply")
    assert apply_response.status_code == 200
    applied = apply_response.json()["data"]
    assert applied["status"] == "APPLIED"
    assert applied["generated_experiment_id"] is not None

    with SessionLocal() as db:
        generated = db.get(ContentExperiment, applied["generated_experiment_id"])
        assert generated.status == "CANDIDATE"
        assert generated.source_type == "OPTIMIZATION_PLAN"
        assert db.query(StrategyMemory).filter(StrategyMemory.account_id == account_id).count() >= 1


def test_post_publish_review_without_metrics_is_inconclusive():
    """测试没有公开指标时复盘结果不会误判成功。"""
    account_id, _, _, published_note_id = create_publish_chain()

    review_response = client.post("/api/reviews", json={"published_note_id": published_note_id})

    assert review_response.status_code == 200
    review = review_response.json()["data"]
    assert review["account_id"] == account_id
    assert review["result_status"] == "INCONCLUSIVE"
    assert any(issue["field"] == "metrics" for issue in review["issues"])


def test_private_conversion_snapshot_rejects_mismatched_account():
    """测试私域转化快照不能绑定到不匹配的账号。"""
    _, _, _, published_note_id = create_publish_chain()
    other_account_id = create_account("other-account")

    response = client.post(
        "/api/conversions/private-snapshots",
        json={
            "account_id": other_account_id,
            "published_note_id": published_note_id,
            "snapshot_window": "24h",
            "lead_count": 1,
        },
    )

    assert response.status_code == 400
    assert "does not match" in response.json()["message"]
