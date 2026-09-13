"""ContextSnapshot slot 级统计报告脚本。"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.context_snapshot import ContextSnapshot
from app.models.context_slot_log import ContextSlotLog
from app.models.prompt_run_log import PromptRunLog


def collect_context_snapshot_metrics(db, limit: int = 100) -> dict:
    """汇总最近若干次 ContextSnapshot / ContextSlotLog 的 slot 级统计指标。"""
    snapshots = (
        db.query(ContextSnapshot)
        .order_by(ContextSnapshot.created_at.desc(), ContextSnapshot.id.desc())
        .limit(limit)
        .all()
    )
    snapshot_ids = [snapshot.id for snapshot in snapshots]
    slot_logs = []
    prompt_logs = []
    if snapshot_ids:
        slot_logs = db.query(ContextSlotLog).filter(ContextSlotLog.context_snapshot_id.in_(snapshot_ids)).all()
        prompt_log_ids = [snapshot.prompt_run_log_id for snapshot in snapshots if snapshot.prompt_run_log_id]
        if prompt_log_ids:
            prompt_logs = db.query(PromptRunLog).filter(PromptRunLog.id.in_(prompt_log_ids)).all()

    metrics = summarize_slot_budget_meta(slot_logs, finalize=False)
    metrics["total_snapshots"] = len(snapshots)
    metrics["snapshot_total_tokens"] = sum(_int(getattr(snapshot, "total_tokens", 0)) for snapshot in snapshots)
    metrics["snapshot_token_budget_total"] = sum(_int(getattr(snapshot, "token_budget", 0)) for snapshot in snapshots)
    _merge_snapshot_breakdown(metrics, snapshots)
    _merge_prompt_slot_budget_summary(metrics, prompt_logs)
    _finalize_metrics(metrics)
    return metrics


def summarize_slot_budget_meta(slot_logs: list, finalize: bool = True) -> dict:
    """汇总 slot budget_meta 中的 token、压缩和筛选指标。"""
    metrics = _empty_metrics()
    metrics["total_slot_logs"] = len(slot_logs)
    for slot in slot_logs:
        slot_name = str(getattr(slot, "slot_name", None) or "unknown")
        metadata = getattr(slot, "metadata_payload", None) or {}
        budget_meta = metadata.get("budget_meta") if isinstance(metadata, dict) else None
        if not isinstance(budget_meta, dict):
            budget_meta = {}
            metrics["missing_budget_meta_count"] += 1
        _apply_slot_values(metrics, slot_name, budget_meta, slot)
    if finalize:
        _finalize_metrics(metrics)
    return metrics


def render_context_snapshot_report(metrics: dict) -> str:
    """把上下文统计指标渲染为 Markdown 报告。"""
    lines = [
        "# 第 5.6 ContextSnapshot 对比报告",
        "",
        "## 1. 报告目的",
        "",
        "第 5.5 已经完成竞品证据、策略记忆、评论洞察的上下文治理。第 5.6 用来统计治理后的 slot token、压缩方法、选中数量、丢弃数量等指标。",
        "",
        "## 2. 数据来源",
        "",
        "主要来自 `ContextSlotLog.metadata_payload[\"budget_meta\"]`，缺失时兜底读取 `ContextSnapshot.slot_token_breakdown` 和 `PromptRunLog.input_payload[\"_context\"][\"slot_budget_summary\"]`。",
        "",
        "## 3. 当前统计口径",
        "",
        "这是工程统计口径，不等于真实业务效果评估。`token_saved_estimate` 是基于 `before_rough_tokens - after_rough_tokens` 的粗略估算，不是真实 tokenizer 或真实成本下降。",
        "",
        "## 4. Slot 级统计指标",
        "",
        "| Slot | 出现次数 | rough_tokens | over_budget | compressed | compression_method | token_ratio |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    slot_names = sorted(metrics.get("slot_count_by_name", {}))
    for slot_name in slot_names:
        method_text = _method_text(metrics.get("compression_method_by_slot", {}).get(slot_name, {}))
        lines.append(
            "| {slot} | {count} | {tokens} | {over_budget} | {compressed} | {method} | {ratio:.4f} |".format(
                slot=slot_name,
                count=metrics["slot_count_by_name"].get(slot_name, 0),
                tokens=metrics["token_by_slot"].get(slot_name, 0),
                over_budget=metrics["over_budget_by_slot"].get(slot_name, 0),
                compressed=metrics["compressed_by_slot"].get(slot_name, 0),
                method=method_text,
                ratio=metrics.get("token_ratio_by_slot", {}).get(slot_name, 0),
            )
        )

    lines.extend(
        [
            "",
            "## 5. 压缩 / 筛选方法分布",
            "",
            _counter_block(metrics.get("compression_method_count", {})),
            "",
            "## 6. selected_count / dropped_count 统计",
            "",
            f"- selected_count_total：{metrics.get('selected_count_total', 0)}",
            f"- dropped_count_total：{metrics.get('dropped_count_total', 0)}",
            "",
            "## 7. before / after token 估算",
            "",
            f"- before_rough_tokens_total：{metrics.get('before_rough_tokens_total', 0)}",
            f"- after_rough_tokens_total：{metrics.get('after_rough_tokens_total', 0)}",
            f"- token_saved_estimate：{metrics.get('token_saved_estimate', 0)}",
            f"- token_saved_ratio_estimate：{metrics.get('token_saved_ratio_estimate', 0):.4f}",
            "",
            "## 8. data_status / trust_level 分布",
            "",
            "data_status：",
            "",
            _counter_block(metrics.get("data_status_count", {})),
            "",
            "trust_level：",
            "",
            _counter_block(metrics.get("trust_level_count", {})),
            "",
            "## 9. 硬编码领域词命中情况",
            "",
            f"- hardcoded_domain_term_count：{metrics.get('hardcoded_domain_term_count', 0)}",
            f"- warning_count：{metrics.get('warning_count', 0)}",
            "",
            "## 10. 当前可写进简历的内容",
            "",
            "- 设计并实现 Context Slot + Token Budget 机制；",
            "- 对竞品证据、策略记忆、评论洞察分别实现确定性 Top-K / 筛选 / 摘要；",
            "- 通过 ContextSnapshot / ContextSlotLog 记录 slot 级 token、压缩方法、选中数量和丢弃数量；",
            "- 支持上下文治理过程可观测和可复盘。",
            "",
            "## 11. 当前不能写进简历的内容",
            "",
            "- token 成本下降 xx%；",
            "- 延迟降低 xx%；",
            "- 生成质量提升 xx%；",
            "- 转化率提升 xx%。",
            "",
            "这些指标除非后续基于真实样本和多轮运行计算出来，否则不能写成确定效果。",
            "",
            "## 12. 结论",
            "",
            "第 5.6 是指标统计能力，不是效果夸大。后续需要结合真实样本、多次运行和 Eval 才能形成可量化优化结论。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：生成 ContextSnapshot 对比报告。"""
    with SessionLocal() as db:
        metrics = collect_context_snapshot_metrics(db)
    print(render_context_snapshot_report(metrics))


def _empty_metrics() -> dict[str, Any]:
    return {
        "total_snapshots": 0,
        "total_slot_logs": 0,
        "missing_budget_meta_count": 0,
        "slot_count_by_name": defaultdict(int),
        "token_by_slot": defaultdict(int),
        "injected_token_by_slot": defaultdict(int),
        "token_ratio_by_slot": defaultdict(float),
        "over_budget_by_slot": defaultdict(int),
        "compressed_by_slot": defaultdict(int),
        "compression_method_by_slot": defaultdict(Counter),
        "over_budget_count": 0,
        "compressed_count": 0,
        "truncated_count": 0,
        "compression_method_count": Counter(),
        "selected_count_total": 0,
        "dropped_count_total": 0,
        "before_rough_tokens_total": 0,
        "after_rough_tokens_total": 0,
        "token_saved_estimate": 0,
        "token_saved_ratio_estimate": 0.0,
        "data_status_count": Counter(),
        "trust_level_count": Counter(),
        "hardcoded_domain_term_count": 0,
        "warning_count": 0,
        "snapshot_total_tokens": 0,
        "snapshot_token_budget_total": 0,
    }


def _apply_slot_values(metrics: dict, slot_name: str, budget_meta: dict, slot: Any | None = None) -> None:
    metrics["slot_count_by_name"][slot_name] = metrics["slot_count_by_name"].get(slot_name, 0) + 1
    rough_tokens = _int(budget_meta.get("rough_tokens"))
    if not rough_tokens and slot is not None:
        rough_tokens = _int(getattr(slot, "injected_tokens", 0))
    metrics["token_by_slot"][slot_name] = metrics["token_by_slot"].get(slot_name, 0) + rough_tokens
    if slot is not None:
        metrics["injected_token_by_slot"][slot_name] = metrics["injected_token_by_slot"].get(slot_name, 0) + _int(getattr(slot, "injected_tokens", 0))
        metrics["token_ratio_by_slot"][slot_name] = metrics["token_ratio_by_slot"].get(slot_name, 0) + _float(getattr(slot, "token_ratio", 0))
        trust_level = getattr(slot, "trust_level", None)
        if trust_level:
            metrics["trust_level_count"][str(trust_level)] = metrics["trust_level_count"].get(str(trust_level), 0) + 1

    if budget_meta.get("over_budget"):
        metrics["over_budget_count"] += 1
        metrics["over_budget_by_slot"][slot_name] = metrics["over_budget_by_slot"].get(slot_name, 0) + 1
    if budget_meta.get("compressed"):
        metrics["compressed_count"] += 1
        metrics["compressed_by_slot"][slot_name] = metrics["compressed_by_slot"].get(slot_name, 0) + 1
    if budget_meta.get("truncated") or (slot is not None and getattr(slot, "was_truncated", False)):
        metrics["truncated_count"] += 1

    method = budget_meta.get("compression_method")
    if method:
        metrics["compression_method_count"][str(method)] = metrics["compression_method_count"].get(str(method), 0) + 1
        method_by_slot = metrics["compression_method_by_slot"].setdefault(slot_name, Counter())
        method_by_slot[str(method)] = method_by_slot.get(str(method), 0) + 1
    metrics["selected_count_total"] += _int(budget_meta.get("selected_count"))
    metrics["dropped_count_total"] += _int(budget_meta.get("dropped_count"))
    metrics["before_rough_tokens_total"] += _int(budget_meta.get("before_rough_tokens"))
    metrics["after_rough_tokens_total"] += _int(budget_meta.get("after_rough_tokens"))

    data_status = budget_meta.get("data_status")
    if data_status:
        metrics["data_status_count"][str(data_status)] = metrics["data_status_count"].get(str(data_status), 0) + 1
    if budget_meta.get("contains_hardcoded_domain_terms"):
        metrics["hardcoded_domain_term_count"] += 1
    if budget_meta.get("warning"):
        metrics["warning_count"] += 1


def _merge_snapshot_breakdown(metrics: dict, snapshots: list) -> None:
    known_slot_names = set(metrics["slot_count_by_name"])
    for snapshot in snapshots:
        for item in getattr(snapshot, "slot_token_breakdown", None) or []:
            slot_name = item.get("slot_name") or "unknown"
            if slot_name in known_slot_names:
                continue
            fallback_meta = {
                "rough_tokens": item.get("tokens"),
                "budget_tokens": item.get("budget_tokens"),
                "over_budget": item.get("over_budget"),
                "truncated": item.get("truncated"),
            }
            _apply_slot_values(metrics, slot_name, fallback_meta)


def _merge_prompt_slot_budget_summary(metrics: dict, prompt_logs: list) -> None:
    known_slot_names = set(metrics["slot_count_by_name"])
    for log in prompt_logs:
        payload = getattr(log, "input_payload", None) or {}
        summary = ((payload.get("_context") or {}).get("slot_budget_summary") or [])
        for item in summary:
            if not isinstance(item, dict):
                continue
            slot_name = item.get("slot_name") or "unknown"
            if slot_name in known_slot_names:
                continue
            _apply_slot_values(metrics, slot_name, item)


def _finalize_metrics(metrics: dict) -> None:
    saved = metrics["before_rough_tokens_total"] - metrics["after_rough_tokens_total"]
    metrics["token_saved_estimate"] = max(0, saved)
    before = metrics["before_rough_tokens_total"]
    metrics["token_saved_ratio_estimate"] = round(metrics["token_saved_estimate"] / before, 4) if before else 0.0
    for slot_name, ratio in list(metrics["token_ratio_by_slot"].items()):
        count = metrics["slot_count_by_name"].get(slot_name, 0)
        metrics["token_ratio_by_slot"][slot_name] = round(ratio / count, 6) if count else 0
    for key in (
        "slot_count_by_name",
        "token_by_slot",
        "injected_token_by_slot",
        "token_ratio_by_slot",
        "over_budget_by_slot",
        "compressed_by_slot",
        "compression_method_count",
        "data_status_count",
        "trust_level_count",
    ):
        metrics[key] = dict(metrics[key])
    metrics["compression_method_by_slot"] = {slot: dict(counter) for slot, counter in metrics["compression_method_by_slot"].items()}


def _counter_block(counter: dict) -> str:
    if not counter:
        return "- 暂无数据"
    return "\n".join(f"- {key}：{value}" for key, value in sorted(counter.items()))


def _method_text(counter: dict) -> str:
    if not counter:
        return ""
    return ", ".join(f"{key}({value})" for key, value in sorted(counter.items()))


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
