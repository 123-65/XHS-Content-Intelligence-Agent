from copy import deepcopy

from app.context.context_builder import ContextManager
from app.context.context_compressor import select_strategy_memory_items
from app.context.context_slots import ContextSlot, ContextSlotName


def test_strategy_memory_filter_selects_requested_count():
    items = [
        {"summary": "A", "confidence": 0.9, "updated_at": "2026-01-03", "content_pillar": "AI Agent"},
        {"summary": "B", "confidence": 0.8, "updated_at": "2026-01-02", "content_pillar": "AI Agent"},
        {"summary": "C", "confidence": 0.7, "updated_at": "2026-01-01", "content_pillar": "AI Agent"},
    ]

    selected, meta = select_strategy_memory_items(items, top_k=2, query_context={"content_pillar": "AI Agent"})

    assert [item["summary"] for item in selected] == ["A", "B"]
    assert meta["selected_count"] == 2
    assert meta["dropped_count"] == 1
    assert meta["top_k"] == 2


def test_strategy_memory_filter_prefers_high_confidence_when_domain_matches():
    items = [
        {"summary": "低置信同领域", "confidence": 0.4, "content_pillar": "AI Agent"},
        {"summary": "高置信同领域", "confidence": 0.95, "content_pillar": "AI Agent"},
    ]

    selected, _ = select_strategy_memory_items(items, top_k=1, query_context={"content_pillar": "AI Agent"})

    assert selected[0]["summary"] == "高置信同领域"


def test_strategy_memory_filter_prefers_fresher_memory_when_confidence_equal():
    items = [
        {"summary": "旧策略", "confidence": 0.8, "updated_at": "2025-01-01", "content_pillar": "AI Agent"},
        {"summary": "新策略", "confidence": 0.8, "updated_at": "2026-01-01", "content_pillar": "AI Agent"},
    ]

    selected, _ = select_strategy_memory_items(items, top_k=1, query_context={"content_pillar": "AI Agent"})

    assert selected[0]["summary"] == "新策略"


def test_strategy_memory_filter_prefers_query_context_domain_match():
    items = [
        {"summary": "高置信但错领域", "confidence": 0.99, "content_pillar": "穿搭"},
        {"summary": "AI Agent 项目有效表达", "confidence": 0.7, "content_pillar": "AI Agent", "tags": ["项目"]},
    ]

    selected, _ = select_strategy_memory_items(
        items,
        top_k=1,
        query_context={"content_pillar": "AI Agent", "selected_topic": "AI Agent 项目"},
    )

    assert selected[0]["summary"] == "AI Agent 项目有效表达"


def test_strategy_memory_filter_blocks_failed_mock_seed_risk_and_low_confidence_items():
    items = [
        {"summary": "可用策略", "confidence": 0.8, "content_pillar": "AI Agent"},
        {"summary": "失败数据", "confidence": 0.9, "data_status": "FAILED"},
        {"summary": "模拟数据", "confidence": 0.9, "is_mock": True},
        {"summary": "种子样本", "confidence": 0.9, "source_type": "SEED_SAMPLE"},
        {"summary": "高风险", "confidence": 0.9, "risk_blocked": True},
        {"summary": "低置信", "confidence": 0.1},
    ]

    selected, meta = select_strategy_memory_items(items, top_k=5, query_context={"content_pillar": "AI Agent"})

    assert [item["summary"] for item in selected] == ["可用策略"]
    assert meta["drop_reason"]["data_status_failed"] == 1
    assert meta["drop_reason"]["mock"] == 1
    assert meta["drop_reason"]["source_type_seed_sample"] == 1
    assert meta["drop_reason"]["risk_blocked"] == 1
    assert meta["drop_reason"]["low_confidence"] == 1


def test_strategy_memory_filter_blocks_domain_version_mismatch_except_generic_memory():
    items = [
        {"summary": "旧领域版本", "confidence": 0.9, "domain_profile_version": "v1"},
        {"summary": "通用策略", "confidence": 0.7, "domain_profile_version": "v1", "tags": ["通用"]},
        {"summary": "新领域版本", "confidence": 0.8, "domain_profile_version": "v2"},
    ]

    selected, meta = select_strategy_memory_items(items, top_k=5, query_context={"domain_profile_version": "v2"})

    assert [item["summary"] for item in selected] == ["新领域版本", "通用策略"]
    assert meta["drop_reason"]["domain_profile_version_mismatch"] == 1


def test_strategy_memory_filter_keeps_limited_failure_memory():
    items = [
        {"summary": "成功策略 A", "confidence": 0.9, "success_or_failure": "success", "content_pillar": "AI Agent"},
        {"summary": "成功策略 B", "confidence": 0.85, "success_or_failure": "success", "content_pillar": "AI Agent"},
        {"summary": "成功策略 C", "confidence": 0.8, "success_or_failure": "success", "content_pillar": "AI Agent"},
        {"summary": "失败复盘", "confidence": 0.7, "success_or_failure": "failure", "content_pillar": "AI Agent"},
    ]

    selected, meta = select_strategy_memory_items(items, top_k=3, query_context={"content_pillar": "AI Agent"})

    assert "失败复盘" in [item["summary"] for item in selected]
    assert sum(1 for item in selected if item.get("success_or_failure") == "failure") == 1
    assert meta["warning"] == "已保留少量失败复盘，用于避免重复踩坑"


def test_strategy_memory_filter_returns_required_meta_fields():
    items = [
        {"summary": "有效策略", "confidence": 0.8, "content_pillar": "AI Agent"},
        {"summary": "低置信策略", "confidence": 0.1, "content_pillar": "AI Agent"},
    ]

    selected, meta = select_strategy_memory_items(items, top_k=1, query_context={"content_pillar": "AI Agent"})

    assert selected
    assert meta["compressed"] is True
    assert meta["truncated"] is False
    assert meta["compression_method"] == "deterministic_strategy_memory_filter"
    assert meta["before_chars"] > meta["after_chars"]
    assert meta["before_rough_tokens"] >= meta["after_rough_tokens"]
    assert meta["selected_count"] == 1
    assert meta["dropped_count"] == 1
    assert meta["top_k"] == 1
    assert meta["summary_generated"] is False


def test_strategy_memory_filter_does_not_mutate_input_items():
    items = [
        {"summary": "有效策略", "confidence": 0.8, "content_pillar": "AI Agent"},
        {"summary": "低置信策略", "confidence": 0.1, "content_pillar": "AI Agent"},
    ]
    original = deepcopy(items)

    selected, _ = select_strategy_memory_items(items, top_k=1, query_context={"content_pillar": "AI Agent"})
    selected[0]["summary"] = "被测试修改"

    assert items == original


def test_context_manager_applies_strategy_memory_filter_metadata():
    manager = ContextManager(task_name="unit", token_budget=2000)
    manager.add_slot(
        ContextSlot(
            ContextSlotName.STRATEGY_MEMORY,
            [
                {"summary": "AI Agent 项目策略", "confidence": 0.9, "content_pillar": "AI Agent"},
                {"summary": "低置信策略", "confidence": 0.1, "content_pillar": "AI Agent"},
                {"summary": "错领域策略", "confidence": 0.95, "content_pillar": "穿搭"},
            ],
            priority=60,
            source_type="strategy_memory",
            metadata={"top_k": 1, "query_context": {"content_pillar": "AI Agent"}},
        )
    )

    built = manager.build()
    slot = built.slots[0]
    budget_meta = slot.metadata["budget_meta"]

    assert "AI Agent 项目策略" in slot.content
    assert "低置信策略" not in slot.content
    assert budget_meta["compressed"] is True
    assert budget_meta["compression_method"] == "deterministic_strategy_memory_filter"
    assert budget_meta["selected_count"] == 1
    assert budget_meta["dropped_count"] == 2
    assert budget_meta["top_k"] == 1
