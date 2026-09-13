from types import SimpleNamespace

from app.models.context_snapshot import ContextSnapshot
from app.models.context_slot_log import ContextSlotLog
from app.models.prompt_run_log import PromptRunLog
from scripts.context_snapshot_report import (
    collect_context_snapshot_metrics,
    render_context_snapshot_report,
    summarize_slot_budget_meta,
)


def make_slot(slot_name: str, budget_meta: dict | None, **overrides):
    return SimpleNamespace(
        slot_name=slot_name,
        metadata_payload={"budget_meta": budget_meta} if budget_meta is not None else {},
        injected_tokens=overrides.get("injected_tokens", 0),
        trust_level=overrides.get("trust_level", "trusted"),
        was_truncated=overrides.get("was_truncated", False),
        token_ratio=overrides.get("token_ratio", 0),
    )


def test_summarize_slot_budget_meta_counts_token_by_slot():
    metrics = summarize_slot_budget_meta(
        [
            make_slot("system_rules", {"rough_tokens": 10}),
            make_slot("system_rules", {"rough_tokens": 15}),
            make_slot("comment_insight", {"rough_tokens": 8}),
        ]
    )

    assert metrics["token_by_slot"]["system_rules"] == 25
    assert metrics["token_by_slot"]["comment_insight"] == 8
    assert metrics["slot_count_by_name"]["system_rules"] == 2


def test_summarize_slot_budget_meta_counts_compression_and_methods():
    metrics = summarize_slot_budget_meta(
        [
            make_slot(
                "competitor_evidence",
                {
                    "rough_tokens": 20,
                    "compressed": True,
                    "compression_method": "deterministic_top_k",
                },
            ),
            make_slot(
                "strategy_memory",
                {
                    "rough_tokens": 12,
                    "compressed": True,
                    "compression_method": "deterministic_strategy_memory_filter",
                },
            ),
        ]
    )

    assert metrics["compressed_count"] == 2
    assert metrics["compression_method_count"]["deterministic_top_k"] == 1
    assert metrics["compression_method_count"]["deterministic_strategy_memory_filter"] == 1


def test_summarize_slot_budget_meta_counts_selected_dropped_and_before_after_tokens():
    metrics = summarize_slot_budget_meta(
        [
            make_slot(
                "comment_insight",
                {
                    "selected_count": 2,
                    "dropped_count": 5,
                    "before_rough_tokens": 100,
                    "after_rough_tokens": 40,
                    "compressed": True,
                },
            )
        ]
    )

    assert metrics["selected_count_total"] == 2
    assert metrics["dropped_count_total"] == 5
    assert metrics["before_rough_tokens_total"] == 100
    assert metrics["after_rough_tokens_total"] == 40
    assert metrics["token_saved_estimate"] == 60
    assert metrics["token_saved_ratio_estimate"] == 0.6


def test_summarize_slot_budget_meta_counts_status_trust_warnings_and_hardcoded_terms():
    metrics = summarize_slot_budget_meta(
        [
            make_slot(
                "comment_insight",
                {
                    "data_status": "REAL",
                    "contains_hardcoded_domain_terms": True,
                    "warning": "COMMENT_SAMPLE_INSUFFICIENT",
                },
                trust_level="untrusted",
                was_truncated=True,
            ),
            make_slot("strategy_memory", {"data_status": "PARTIAL"}, trust_level="trusted"),
        ]
    )

    assert metrics["data_status_count"]["REAL"] == 1
    assert metrics["data_status_count"]["PARTIAL"] == 1
    assert metrics["trust_level_count"]["untrusted"] == 1
    assert metrics["trust_level_count"]["trusted"] == 1
    assert metrics["hardcoded_domain_term_count"] == 1
    assert metrics["warning_count"] == 1
    assert metrics["truncated_count"] == 1


def test_summarize_slot_budget_meta_tolerates_missing_budget_meta():
    metrics = summarize_slot_budget_meta([make_slot("workflow_state", None, injected_tokens=9)])

    assert metrics["missing_budget_meta_count"] == 1
    assert metrics["token_by_slot"]["workflow_state"] == 9


def test_render_context_snapshot_report_outputs_markdown():
    metrics = summarize_slot_budget_meta(
        [
            make_slot(
                "competitor_evidence",
                {
                    "rough_tokens": 20,
                    "compressed": True,
                    "compression_method": "deterministic_top_k",
                    "selected_count": 1,
                    "dropped_count": 2,
                },
                trust_level="untrusted",
            )
        ]
    )
    metrics["total_snapshots"] = 1

    markdown = render_context_snapshot_report(metrics)

    assert markdown.startswith("# 第 5.6 ContextSnapshot 对比报告")
    assert "| competitor_evidence |" in markdown
    assert "deterministic_top_k" in markdown
    assert "token_saved_estimate" in markdown


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def order_by(self, *args):
        return self

    def limit(self, limit):
        self.rows = self.rows[:limit]
        return self

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class FakeDb:
    def __init__(self, snapshots, slot_logs, prompt_logs):
        self.snapshots = snapshots
        self.slot_logs = slot_logs
        self.prompt_logs = prompt_logs

    def query(self, model):
        if model is ContextSnapshot:
            return FakeQuery(self.snapshots)
        if model is ContextSlotLog:
            return FakeQuery(self.slot_logs)
        if model is PromptRunLog:
            return FakeQuery(self.prompt_logs)
        return FakeQuery([])


def test_collect_context_snapshot_metrics_uses_snapshot_and_prompt_fallbacks():
    snapshot = SimpleNamespace(
        id=1,
        prompt_run_log_id=10,
        total_tokens=100,
        token_budget=600,
        slot_token_breakdown=[
            {"slot_name": "snapshot_only", "tokens": 11, "budget_tokens": 20, "over_budget": False, "truncated": False}
        ],
    )
    prompt_log = SimpleNamespace(
        id=10,
        input_payload={
            "_context": {
                "slot_budget_summary": [
                    {"slot_name": "prompt_only", "rough_tokens": 7, "compressed": False, "data_status": "NOT_PROVIDED"}
                ]
            }
        },
    )

    metrics = collect_context_snapshot_metrics(FakeDb([snapshot], [], [prompt_log]), limit=10)

    assert metrics["total_snapshots"] == 1
    assert metrics["total_slot_logs"] == 0
    assert metrics["token_by_slot"]["snapshot_only"] == 11
    assert metrics["token_by_slot"]["prompt_only"] == 7
