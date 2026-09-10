from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": "V2实验测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/experiment-v2-test",
            "content_domain": "AI Agent",
            "positioning": "帮助普通大学生做能写进简历的 AI Agent 项目",
            "target_audience": "大学生、转码初学者、27届应届生",
            "persona": "实话型项目学姐",
            "monetization_goal": "资料包和咨询转化",
            "business_model": "资料包 / 咨询",
            "main_product": "AI Agent 项目资料包",
            "lead_value": 15,
            "avg_order_value": 99,
            "gross_profit": 80,
            "primary_goal": "lead",
            "tone_preference": "通俗直接",
            "forbidden_topics": "不夸大收益",
            "account_stage": "STARTUP",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_content_opportunities(account_id: int) -> int:
    """通过采集和竞品分析创建内容机会并返回报告 ID。"""
    create_manual_competitor_data(account_id)

    report_response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "实验前置内容机会", "keyword": "AI Agent"},
    )
    assert report_response.status_code == 200
    return report_response.json()["data"]["id"]


def create_manual_competitor_data(account_id: int) -> None:
    """写入非 Mock 竞品数据，匹配 V2 报告入口的数据契约。"""
    with SessionLocal() as db:
        competitor_account = CompetitorAccount(
            account_id=account_id,
            platform_account_id=f"manual-experiment-account-{account_id}",
            nickname="AI Agent 项目学姐",
            homepage_url="https://www.xiaohongshu.com/user/profile/manual-experiment-agent",
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
                note_id=f"manual-experiment-note-{account_id}-001",
                note_url="https://www.xiaohongshu.com/explore/manual-experiment-agent-001",
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
                note_id=f"manual-experiment-note-{account_id}-002",
                note_url="https://www.xiaohongshu.com/explore/manual-experiment-agent-002",
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
                note_id=f"manual-experiment-note-{account_id}-003",
                note_url="https://www.xiaohongshu.com/explore/manual-experiment-agent-003",
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
                    comment_id=f"manual-experiment-comment-{account_id}-001",
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
                    comment_id=f"manual-experiment-comment-{account_id}-002",
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
                    comment_id=f"manual-experiment-comment-{account_id}-003",
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


def test_generate_experiment_cards_from_opportunities():
    """测试从内容机会生成候选实验卡。"""
    account_id = create_test_account()
    report_id = create_content_opportunities(account_id)

    response = client.post(
        "/api/experiments/generate",
        json={"account_id": account_id, "report_id": report_id, "limit": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == account_id
    assert data["count"] == 3

    first = data["experiments"][0]
    assert first["status"] == "CANDIDATE"
    assert first["experiment_name"]
    assert first["hypothesis"]
    assert first["content_pillar"]
    assert first["content_format"]
    assert first["main_variable"]
    assert first["control_variables"]
    assert first["primary_metric"]
    assert first["secondary_metrics"]
    assert first["success_criteria"]
    assert first["failure_criteria"]
    assert first["fallback_strategy"]
    assert first["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert first["variables"]
    assert first["metric_targets"]
    assert any(item["variable_name"] == "cta_strength" and item["variable_value"]["value"] == "SOFT" for item in first["variables"])


def test_get_list_and_approve_experiment_card():
    """测试查询和审批候选实验卡。"""
    account_id = create_test_account()
    report_id = create_content_opportunities(account_id)
    generate_response = client.post(
        "/api/experiments/generate",
        json={"account_id": account_id, "report_id": report_id, "limit": 3},
    )
    experiment_id = generate_response.json()["data"]["experiments"][0]["id"]

    list_response = client.get(f"/api/experiments?account_id={account_id}")
    assert list_response.status_code == 200
    assert any(item["id"] == experiment_id for item in list_response.json()["data"])

    detail_response = client.get(f"/api/experiments/{experiment_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == experiment_id

    approve_response = client.post(f"/api/experiments/{experiment_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "APPROVED"
