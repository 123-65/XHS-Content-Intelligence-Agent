from copy import deepcopy

from app.context.context_compressor import select_competitor_evidence_top_k


def test_competitor_evidence_top_k_selects_requested_count():
    items = [
        {"title": "A", "data_status": "REAL", "collect_count": 10, "like_count": 10, "comment_count": 1},
        {"title": "B", "data_status": "REAL", "collect_count": 9, "like_count": 10, "comment_count": 1},
        {"title": "C", "data_status": "REAL", "collect_count": 8, "like_count": 10, "comment_count": 1},
    ]

    selected, meta = select_competitor_evidence_top_k(items, top_k=2)

    assert [item["title"] for item in selected] == ["A", "B"]
    assert meta["selected_count"] == 2
    assert meta["dropped_count"] == 1
    assert meta["top_k"] == 2


def test_competitor_evidence_top_k_filters_mock_failed_and_high_risk_items():
    items = [
        {"title": "真实证据", "data_status": "REAL", "collect_count": 5},
        {"title": "模拟证据", "data_status": "REAL", "is_mock": True, "collect_count": 999},
        {"title": "失败证据", "data_status": "FAILED", "collect_count": 888},
        {"title": "高风险证据", "data_status": "REAL", "risk_level": "HIGH", "collect_count": 777},
    ]

    selected, meta = select_competitor_evidence_top_k(items, top_k=5)

    assert [item["title"] for item in selected] == ["真实证据"]
    assert meta["drop_reason"]["mock"] == 1
    assert meta["drop_reason"]["data_status_failed"] == 1
    assert meta["drop_reason"]["high_risk"] == 1


def test_competitor_evidence_top_k_prefers_keyword_relevance():
    items = [
        {
            "title": "高互动但不相关",
            "content": "泛泛的生活记录",
            "data_status": "REAL",
            "collect_count": 999,
            "like_count": 999,
        },
        {
            "title": "AI Agent 项目复盘",
            "content": "完整拆解 AI Agent 项目怎么做",
            "tags": ["AI Agent", "项目"],
            "data_status": "REAL",
            "collect_count": 1,
            "like_count": 1,
        },
    ]

    selected, _ = select_competitor_evidence_top_k(
        items,
        top_k=1,
        query_context={"selected_topic": "AI Agent 项目", "domain_keywords": ["AI Agent"]},
    )

    assert selected[0]["title"] == "AI Agent 项目复盘"


def test_competitor_evidence_top_k_prefers_engagement_when_trust_and_relevance_equal():
    items = [
        {"title": "低互动", "data_status": "REAL", "collect_count": 1, "like_count": 1, "comment_count": 1},
        {"title": "高收藏", "data_status": "REAL", "collect_count": 20, "like_count": 1, "comment_count": 1},
        {"title": "高点赞", "data_status": "REAL", "collect_count": 1, "like_count": 20, "comment_count": 1},
    ]

    selected, _ = select_competitor_evidence_top_k(items, top_k=1)

    assert selected[0]["title"] == "高收藏"


def test_competitor_evidence_top_k_returns_required_meta_fields():
    items = [
        {"title": "真实证据", "data_status": "REAL", "collect_count": 5},
        {"title": "模拟证据", "is_mock": True, "collect_count": 999},
    ]

    selected, meta = select_competitor_evidence_top_k(items, top_k=1)

    assert selected
    assert meta["compressed"] is True
    assert meta["truncated"] is False
    assert meta["compression_method"] == "deterministic_top_k"
    assert meta["before_chars"] > meta["after_chars"]
    assert meta["before_rough_tokens"] >= meta["after_rough_tokens"]
    assert meta["selected_count"] == 1
    assert meta["dropped_count"] == 1
    assert meta["top_k"] == 1
    assert meta["summary_generated"] is False


def test_competitor_evidence_top_k_does_not_mutate_input_items():
    items = [
        {"title": "真实证据", "data_status": "REAL", "collect_count": 5},
        {"title": "模拟证据", "is_mock": True, "collect_count": 999},
    ]
    original = deepcopy(items)

    selected, _ = select_competitor_evidence_top_k(items, top_k=1)
    selected[0]["title"] = "被测试修改"

    assert items == original
