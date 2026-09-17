from fastapi.testclient import TestClient
from app.core.database import SessionLocal

from app.enums.competitor_analysis import CommentDemandType, RiskLevel
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_note import CompetitorNote
from app.models.competitor_comment import CompetitorComment
from app.main import app

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": "V2竞品分析测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/report-v2-test",
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
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_manual_competitor_data(account_id: int) -> None:
    """写入手动真实样本风格的竞品数据，不再依赖 SeedSampleProvider。"""
    with SessionLocal() as db:
        competitor_account = CompetitorAccount(
            account_id=account_id,
            platform_account_id=f"manual-account-{account_id}",
            nickname="AI Agent 项目学姐",
            homepage_url="https://www.xiaohongshu.com/user/profile/manual-agent-project",
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
                note_id=f"manual-note-{account_id}-001",
                note_url="https://www.xiaohongshu.com/explore/manual-agent-project-001",
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
                raw_snapshot={
                    "source": "manual_test_fixture",
                    "note": "测试用手动样本，不经过 SeedSampleProvider",
                },
            ),
            CompetitorNote(
                account_id=account_id,
                competitor_account_id=competitor_account.id,
                note_id=f"manual-note-{account_id}-002",
                note_url="https://www.xiaohongshu.com/explore/manual-agent-project-002",
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
                note_id=f"manual-note-{account_id}-003",
                note_url="https://www.xiaohongshu.com/explore/manual-agent-project-003",
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
        comments = [
            CompetitorComment(
                account_id=account_id,
                competitor_note_id=notes[0].id,
                comment_id=f"manual-comment-{account_id}-001",
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
                comment_id=f"manual-comment-{account_id}-002",
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
                comment_id=f"manual-comment-{account_id}-003",
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
        db.add_all(comments)
        db.commit()


def create_mock_competitor_note(account_id: int) -> None:
    """写入 Mock 笔记，用于验证真实报告不会误用 Mock 数据。"""
    with SessionLocal() as db:
        db.add(
            CompetitorNote(
                account_id=account_id,
                competitor_account_id=None,
                note_id=f"mock-note-{account_id}-001",
                note_url="https://www.xiaohongshu.com/explore/mock-agent-project-001",
                author_name="Mock AI账号",
                title="AI Agent Mock 项目路线",
                content="这是一条 Mock 竞品笔记，不能用于真实竞品分析。",
                tags=["AI Agent", "Mock"],
                like_count=100,
                collect_count=80,
                comment_count=10,
                source_type="SEED_SAMPLE",
                provider_name="seed_sample",
                is_mock=True,
                confidence=0.8,
                raw_snapshot={"source": "mock_test_fixture"},
            )
        )
        db.commit()


def test_create_competitor_report_v2():
    """测试创建 V2 竞品与爆款分析报告。"""
    account_id = create_test_account()
    create_manual_competitor_data(account_id)

    response = client.post(
        "/api/competitor/reports",
        json={
            "account_id": account_id,
            "name": "AI Agent 竞品与爆款分析",
            "keyword": "AI Agent",
            "target_metric": "engagement",
            "limit": 20,
            "analysis_engine": "RULE_BASELINE",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == account_id
    assert data["source_type"] == "COMPETITOR_COLLECTION"
    assert data["note_count"] == 3
    assert data["comment_count"] == 3
    assert data["persona_patterns"]
    assert data["content_pillars"]
    assert data["title_patterns"]
    assert data["cover_patterns"]
    assert data["content_structures"]
    assert data["comment_demands"]
    assert data["conversion_signals"]
    assert "avg_score" in data["replicability_summary"]
    assert data["risk_points"]


def test_create_report_without_notes_returns_business_state():
    """测试完全没有竞品笔记时返回可行动的业务状态。"""
    account_id = create_test_account()

    response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "空数据报告", "keyword": "AI Agent"},
    )

    assert response.status_code == 400
    data = response.json()["data"]
    assert data["data_quality"] == "EMPTY"
    assert data["reason"] == "NO_COMPETITOR_NOTES"
    assert data["action"] == "COLLECT_COMPETITOR_NOTES"
    assert data["can_continue"] is False
    assert data["counts"]["total_count"] == 0
    assert data["hint"]


def test_create_report_with_only_mock_notes_returns_business_state():
    """测试只有 Mock 笔记时不会生成真实竞品报告。"""
    account_id = create_test_account()
    create_mock_competitor_note(account_id)

    response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "Mock 数据报告", "keyword": "AI Agent"},
    )

    assert response.status_code == 400
    data = response.json()["data"]
    assert data["data_quality"] == "EMPTY"
    assert data["reason"] == "ONLY_MOCK_COMPETITOR_NOTES"
    assert data["action"] == "REPLACE_WITH_REAL_NOTES"
    assert data["counts"]["total_count"] == 1
    assert data["counts"]["real_count"] == 0


def test_create_report_keyword_no_match_returns_business_state():
    """测试关键词没有命中真实笔记时提示调整关键词或补采集。"""
    account_id = create_test_account()
    create_manual_competitor_data(account_id)

    response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "关键词未命中报告", "keyword": "Rust"},
    )

    assert response.status_code == 400
    data = response.json()["data"]
    assert data["data_quality"] == "EMPTY"
    assert data["reason"] == "KEYWORD_NO_MATCH"
    assert data["action"] == "RELAX_KEYWORD_OR_COLLECT_MORE"
    assert data["counts"]["real_count"] == 3
    assert data["counts"]["keyword_real_count"] == 0


def test_get_viral_notes_and_opportunities():
    """测试查询爆款笔记拆解和内容机会。"""
    account_id = create_test_account()
    create_manual_competitor_data(account_id)
    report_response = client.post(
        "/api/competitor/reports",
        json={
            "account_id": account_id,
            "name": "内容机会分析",
            "keyword": "AI Agent",
            "analysis_engine": "RULE_BASELINE",
        },
    )
    report_id = report_response.json()["data"]["id"]

    detail_response = client.get(f"/api/competitor/reports/{report_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == report_id

    viral_response = client.get(f"/api/competitor/reports/{report_id}/viral-notes")
    assert viral_response.status_code == 200
    viral_notes = viral_response.json()["data"]
    assert len(viral_notes) >= 1
    assert viral_notes[0]["evidence_summary"]
    assert viral_notes[0]["replicability_score"] >= 0
    assert isinstance(viral_notes[0]["comment_demands"], list)

    opportunities_response = client.get(f"/api/competitor/reports/{report_id}/opportunities")
    assert opportunities_response.status_code == 200
    opportunities = opportunities_response.json()["data"]
    assert len(opportunities) >= 1
    first = opportunities[0]
    assert first["evidence_summary"]
    assert first["comment_demand_type"] in {item.value for item in CommentDemandType}
    assert first["risk_level"] in {item.value for item in RiskLevel}
    assert 0 <= first["replicability_score"] <= 100
    assert 0 <= first["opportunity_score"] <= 100
