from app.context.context_budget import (
    SLOT_BUDGETS,
    build_slot_budget_meta,
    contains_hardcoded_domain_terms,
    rough_token_count,
    slot_budget_for,
)


def test_rough_token_count_returns_positive_integer():
    tokens = rough_token_count("中文内容 mixed English content")

    assert isinstance(tokens, int)
    assert tokens > 0


def test_all_designed_slots_have_budget_config():
    expected_slots = {
        "SYSTEM_RULES",
        "TASK_INSTRUCTION",
        "USER_INPUT",
        "ACCOUNT_PROFILE",
        "DOMAIN_PROFILE",
        "WORKFLOW_STATE",
        "COMPETITOR_EVIDENCE",
        "COMMENT_INSIGHT",
        "STRATEGY_MEMORY",
        "RISK_CONSTRAINTS",
        "OUTPUT_SCHEMA",
        "DRAFT_CONTENT",
    }

    assert expected_slots.issubset(SLOT_BUDGETS)
    for slot_name in expected_slots:
        budget = slot_budget_for(slot_name)
        assert budget["budget_tokens"] > 0
        assert "required" in budget
        assert "compressible" in budget
        assert "trimmable" in budget
        assert budget["priority"]
        assert budget["missing_policy"]


def test_build_slot_budget_meta_calculates_budget_fields():
    meta = build_slot_budget_meta(
        "ACCOUNT_PROFILE",
        {"account_name": "demo", "positioning": "AI Agent 项目账号"},
        source="account_profile",
        source_version="v1",
    )

    assert meta["slot_name"] == "ACCOUNT_PROFILE"
    assert meta["source"] == "account_profile"
    assert meta["chars"] > 0
    assert meta["rough_tokens"] > 0
    assert meta["budget_tokens"] == 500
    assert meta["required"] is True
    assert meta["compressible"] is True
    assert meta["trimmable"] is True
    assert meta["source_version"] == "v1"
    assert meta["source_label"] == "账号画像"
    assert meta["priority_label"] == "P0 必须保留"
    assert meta["missing_policy_label"] == "阻断或要求补充"
    assert meta["data_status_label"] == "真实数据"
    assert "账号画像" in meta["description"]


def test_over_budget_only_marks_metadata_without_changing_content():
    content = "项目实战" * 1000
    meta = build_slot_budget_meta("USER_INPUT", content)

    assert content == "项目实战" * 1000
    assert meta["over_budget"] is True
    assert meta["compressed"] is False
    assert meta["truncated"] is False
    assert "后续第 5.5" in meta["warning"]


def test_hardcoded_domain_terms_are_marked_only():
    assert contains_hardcoded_domain_terms("这是一条 AI Agent 项目实战内容") is True
    assert contains_hardcoded_domain_terms("这是一条摄影约拍档期内容") is False

    meta = build_slot_budget_meta("WORKFLOW_STATE", "双非学生做 Agent 项目")
    assert meta["contains_hardcoded_domain_terms"] is True
