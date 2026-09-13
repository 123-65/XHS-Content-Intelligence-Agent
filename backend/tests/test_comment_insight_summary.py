from copy import deepcopy

from app.context.context_builder import ContextManager
from app.context.context_compressor import summarize_comment_insights
from app.context.context_slots import ContextSlot, ContextSlotName, ContextTrustLevel


def test_comment_insight_summary_keeps_top_demands():
    items = [
        {"item_type": "demand", "type": "PROJECT_STRUCTURE", "count": 5, "examples": ["想看项目结构"]},
        {"item_type": "demand", "type": "SOURCE_CODE", "count": 4, "examples": ["源码在哪"]},
        {"item_type": "demand", "type": "INTERVIEW", "count": 3, "examples": ["面试怎么讲"]},
        {"item_type": "demand", "type": "PRICE", "count": 2, "examples": ["资料多少钱"]},
        {"item_type": "demand", "type": "OTHER", "count": 1, "examples": ["其他问题"]},
        {"item_type": "demand", "type": "EXTRA", "count": 1, "examples": ["额外问题"]},
        {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "想看完整项目结构", "like_count": 9, "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "源码可以给吗", "like_count": 8, "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "INTERVIEW", "content": "面试官会问什么", "like_count": 7, "data_status": "REAL"},
    ]

    summary, meta = summarize_comment_insights(items, top_k=6)

    assert [item["type"] for item in summary["demand_summary"]] == [
        "PROJECT_STRUCTURE",
        "SOURCE_CODE",
        "INTERVIEW",
        "PRICE",
        "OTHER",
    ]
    assert meta["demand_count"] == 5


def test_comment_insight_summary_limits_representative_comments():
    items = [
        {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": f"评论 {index}", "like_count": index, "data_status": "REAL"}
        for index in range(10)
    ]

    summary, meta = summarize_comment_insights(items, top_k=3)

    assert len(summary["representative_comments"]) == 2
    assert all("untrusted_text" in item for item in summary["representative_comments"])
    assert meta["selected_count"] == 2
    assert meta["dropped_count"] == 8


def test_comment_insight_summary_keeps_conversion_signals_and_risks():
    items = [
        {"item_type": "conversion_signal", "name": "求源码", "count": 4},
        {"item_type": "conversion_signal", "name": "要资料", "count": 3},
        {"item_type": "risk_point", "name": "夸大收益", "count": 2},
        {"item_type": "risk_point", "name": "强诱导评论", "count": 1},
        {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "源码可以发吗", "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "想要代码", "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "RESOURCE", "content": "资料怎么领", "data_status": "REAL"},
    ]

    summary, meta = summarize_comment_insights(items, top_k=6)

    assert summary["conversion_signal_summary"][0] == {"name": "求源码", "count": 4}
    assert summary["risk_summary"][0] == {"name": "夸大收益", "count": 2}
    assert meta["conversion_signal_count"] == 2
    assert meta["risk_count"] == 2


def test_comment_insight_summary_marks_insufficient_comment_samples():
    items = [
        {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "源码在哪", "data_status": "REAL"},
    ]

    summary, meta = summarize_comment_insights(items, top_k=6)

    assert summary["data_status"] == "DATA_INSUFFICIENT"
    assert meta["warning"] == "COMMENT_SAMPLE_INSUFFICIENT"
    assert meta["drop_reason"]["comment_sample_insufficient"] == 1


def test_comment_insight_summary_returns_required_meta_fields():
    items = [
        {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "源码在哪", "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "项目结构怎么拆", "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "想看结构图", "data_status": "REAL"},
    ]

    summary, meta = summarize_comment_insights(items, top_k=2)

    assert summary["data_status"] == "REAL"
    assert meta["compressed"] is True
    assert meta["truncated"] is False
    assert meta["compression_method"] == "deterministic_comment_insight_summary"
    assert meta["before_chars"] > 0
    assert meta["after_chars"] > 0
    assert meta["before_rough_tokens"] > 0
    assert meta["after_rough_tokens"] > 0
    assert meta["selected_count"] == 2
    assert meta["dropped_count"] == 1
    assert meta["top_k"] == 2
    assert meta["summary_generated"] is True


def test_comment_insight_summary_does_not_mutate_input_items():
    items = [
        {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "源码在哪", "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "项目结构怎么拆", "data_status": "REAL"},
        {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "想看结构图", "data_status": "REAL"},
    ]
    original = deepcopy(items)

    summary, _ = summarize_comment_insights(items, top_k=2)
    summary["representative_comments"][0]["untrusted_text"] = "被测试修改"

    assert items == original


def test_context_manager_applies_comment_insight_summary_and_untrusted_metadata():
    manager = ContextManager(task_name="unit", token_budget=2000)
    manager.add_slot(
        ContextSlot(
            ContextSlotName.COMMENT_INSIGHT,
            [
                {"item_type": "comment", "demand_type": "SOURCE_CODE", "content": "源码在哪", "like_count": 3, "data_status": "REAL"},
                {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "项目结构怎么拆", "like_count": 5, "data_status": "REAL"},
                {"item_type": "comment", "demand_type": "PROJECT_STRUCTURE", "content": "想看结构图", "like_count": 4, "data_status": "REAL"},
                {"item_type": "conversion_signal", "name": "求源码", "count": 2},
                {"item_type": "risk_point", "name": "强诱导评论", "count": 1},
            ],
            priority=70,
            source_type="comment_insight",
            trust_level=ContextTrustLevel.UNTRUSTED,
            metadata={"top_k": 2, "data_status": "REAL"},
        )
    )

    built = manager.build()
    slot = built.slots[0]
    budget_meta = slot.metadata["budget_meta"]

    assert slot.trust_level == "untrusted"
    assert "UNTRUSTED_SOURCE:comment_insight" in slot.content
    assert "untrusted_text" in slot.content
    assert budget_meta["compressed"] is True
    assert budget_meta["compression_method"] == "deterministic_comment_insight_summary"
    assert budget_meta["summary_generated"] is True
    assert budget_meta["selected_count"] == 2
    assert budget_meta["dropped_count"] == 1
