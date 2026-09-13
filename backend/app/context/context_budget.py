from dataclasses import dataclass
import json
from typing import Any

from app.context.context_slots import BuiltContextSlot


DEFAULT_CONTEXT_BUDGETS = {
    "default": 4000,
    "draft_generation": 6000,
    "draft_regeneration": 5000,
    "competitor_analysis": 7000,
    "review_report": 6000,
    "agent_step": 3000,
}

SLOT_BUDGETS: dict[str, dict[str, Any]] = {
    "SYSTEM_RULES": {
        "budget_tokens": 300,
        "required": True,
        "compressible": False,
        "trimmable": False,
        "priority": "P0_REQUIRED",
        "missing_policy": "BLOCK",
        "description": "系统规则，控制模型行为边界，必须保留",
    },
    "TASK_INSTRUCTION": {
        "budget_tokens": 300,
        "required": True,
        "compressible": False,
        "trimmable": False,
        "priority": "P0_REQUIRED",
        "missing_policy": "BLOCK",
        "description": "任务说明，告诉模型本次要完成什么，必须保留",
    },
    "USER_INPUT": {
        "budget_tokens": 500,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P0_CONTEXT",
        "missing_policy": "ALLOW_EMPTY",
        "description": "用户本轮输入或人工补充要求，原文优先",
    },
    "ACCOUNT_PROFILE": {
        "budget_tokens": 500,
        "required": True,
        "compressible": True,
        "trimmable": True,
        "priority": "P0_REQUIRED",
        "missing_policy": "BLOCK_OR_REQUEST_INPUT",
        "description": "账号画像，承载定位、人群、目标和语气等关键字段",
    },
    "DOMAIN_PROFILE": {
        "budget_tokens": 700,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P0_CONTEXT",
        "missing_policy": "UNKNOWN",
        "description": "领域画像，承载领域词、风险词、转化词和版本信息",
    },
    "WORKFLOW_STATE": {
        "budget_tokens": 800,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P0_CONTEXT",
        "missing_policy": "DATA_PARTIAL",
        "description": "流程状态，承载当前实验、机会、选题和指标",
    },
    "COMPETITOR_EVIDENCE": {
        "budget_tokens": 1200,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P1_EVIDENCE",
        "missing_policy": "DATA_NOT_PROVIDED",
        "description": "竞品证据，后续优先做 Top-K 和摘要",
    },
    "COMMENT_INSIGHT": {
        "budget_tokens": 800,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P1_EVIDENCE",
        "missing_policy": "DATA_NOT_PROVIDED",
        "description": "评论洞察，后续保留需求分类、计数和代表评论",
    },
    "STRATEGY_MEMORY": {
        "budget_tokens": 600,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P1_MEMORY",
        "missing_policy": "NOT_PROVIDED",
        "description": "策略记忆，后续按置信度、新鲜度和同领域匹配筛选",
    },
    "RISK_CONSTRAINTS": {
        "budget_tokens": 500,
        "required": True,
        "compressible": False,
        "trimmable": True,
        "priority": "P0_REQUIRED",
        "missing_policy": "FALLBACK_GENERIC_RULES",
        "description": "风险约束，承载平台、账号和领域风险边界",
    },
    "OUTPUT_SCHEMA": {
        "budget_tokens": 800,
        "required": True,
        "compressible": False,
        "trimmable": False,
        "priority": "P0_REQUIRED",
        "missing_policy": "BLOCK",
        "description": "输出结构，承载 JSON schema 和字段约束，必须保留",
    },
    "DRAFT_CONTENT": {
        "budget_tokens": 1200,
        "required": False,
        "compressible": True,
        "trimmable": True,
        "priority": "P0_CONTEXT",
        "missing_policy": "BLOCK_FOR_REVIEW_ONLY",
        "description": "草稿内容，审核任务中必须保留待审核正文核心",
    },
}

DEFAULT_SLOT_BUDGET = {
    "budget_tokens": 400,
    "required": False,
    "compressible": True,
    "trimmable": True,
    "priority": "OPTIONAL",
    "missing_policy": "NOT_PROVIDED",
    "description": "未配置的普通上下文槽位，使用默认预算",
}

PRIORITY_LABELS = {
    "P0_REQUIRED": "P0 必须保留",
    "P0_CONTEXT": "P0 重要上下文",
    "P1_EVIDENCE": "P1 上游证据",
    "P1_MEMORY": "P1 策略记忆",
    "OPTIONAL": "可选上下文",
}

MISSING_POLICY_LABELS = {
    "BLOCK": "缺失时阻断",
    "ALLOW_EMPTY": "允许为空",
    "BLOCK_OR_REQUEST_INPUT": "阻断或要求补充",
    "UNKNOWN": "允许继续并标记为未知",
    "DATA_PARTIAL": "允许继续并标记为数据不完整",
    "DATA_NOT_PROVIDED": "允许继续并标记为未提供数据",
    "NOT_PROVIDED": "允许继续并标记为未提供",
    "FALLBACK_GENERIC_RULES": "使用通用规则兜底",
    "BLOCK_FOR_REVIEW_ONLY": "审核任务缺失时阻断",
}

SOURCE_LABELS = {
    "internal": "内部上下文",
    "prompt_template": "提示词模板",
    "risk_constraints": "风险约束配置",
    "account_profile": "账号画像",
    "content_experiment_v2": "内容实验 V2",
    "manual_input": "用户人工输入",
    "schema_model": "结构化输出模型",
    "strategy_memory": "策略记忆",
    "competitor_report": "竞品报告",
    "competitor_analysis": "竞品分析",
    "rule_based": "规则输出",
}

DATA_STATUS_LABELS = {
    "REAL": "真实数据",
    "PARTIAL": "部分数据",
    "NOT_PROVIDED": "未提供",
    "UNKNOWN": "未知",
    "MANUAL": "人工输入",
    "MOCK": "模拟数据",
    "UNCONFIRMED": "未人工确认",
}

HARDCODED_DOMAIN_TERMS = [
    "大学生",
    "双非",
    "27届",
    "小白",
    "新手",
    "零基础",
    "Agent",
    "AI Agent",
    "项目",
    "实战",
    "简历",
    "面试",
    "上岸",
    "求职",
    "学习路线",
    "源码",
    "github",
    "课程",
    "普通本科",
    "转码",
    "应届生",
]


def rough_token_count(text: str | None) -> int:
    """粗略估算文本 token 数：中文约 1.5 字符算 1 token，英文和符号约 4 字符算 1 token。"""
    if not text:
        return 0
    cjk_chars = sum(1 for char in text if _is_cjk_char(char))
    other_chars = len(text) - cjk_chars
    cjk_tokens = (cjk_chars * 2 + 2) // 3
    other_tokens = (other_chars + 3) // 4
    return max(1, cjk_tokens + other_tokens)


def contains_hardcoded_domain_terms(text: str | None) -> bool:
    """判断上下文文本是否包含当前 demo 赛道硬编码领域词；本阶段只标记，不替换。"""
    if not text:
        return False
    lowered = text.lower()
    return any(term.lower() in lowered for term in HARDCODED_DOMAIN_TERMS)


def build_slot_budget_meta(
    slot_name: str,
    content: Any,
    source: str | None = None,
    source_version: str | None = None,
    data_status: str | None = None,
) -> dict[str, Any]:
    """构建单个上下文槽位的预算统计元数据，只记录预算状态，不压缩、不截断原文。"""
    rendered = _render_for_budget(content)
    chars = len(rendered)
    rough_tokens = rough_token_count(rendered)
    budget = slot_budget_for(slot_name)
    budget_tokens = int(budget["budget_tokens"])
    over_budget = rough_tokens > budget_tokens
    resolved_data_status = data_status or ("NOT_PROVIDED" if chars == 0 else "REAL")
    warnings: list[str] = []

    if budget is DEFAULT_SLOT_BUDGET:
        warnings.append("当前 slot 未配置预算，使用默认预算")
    if budget["required"] and chars == 0:
        warnings.append("必需 slot 缺失或为空")
    if over_budget:
        warnings.append("当前 slot 超过预算，后续第 5.5 再处理压缩或 Top-K")

    return {
        "slot_name": _slot_name_to_text(slot_name),
        "source": source or "internal",
        "source_label": SOURCE_LABELS.get(source or "internal", "其他来源"),
        "chars": chars,
        "rough_tokens": rough_tokens,
        "budget_tokens": budget_tokens,
        "over_budget": over_budget,
        "priority": budget["priority"],
        "priority_label": PRIORITY_LABELS.get(str(budget["priority"]), "未分类优先级"),
        "required": bool(budget["required"]),
        "compressible": bool(budget["compressible"]),
        "trimmable": bool(budget["trimmable"]),
        "compressed": False,
        "truncated": False,
        "data_status": resolved_data_status,
        "data_status_label": DATA_STATUS_LABELS.get(resolved_data_status, "其他状态"),
        "contains_hardcoded_domain_terms": contains_hardcoded_domain_terms(rendered),
        "source_version": source_version,
        "missing_policy": budget["missing_policy"],
        "missing_policy_label": MISSING_POLICY_LABELS.get(str(budget["missing_policy"]), "未分类缺失策略"),
        "description": budget.get("description"),
        "warning": "；".join(warnings) if warnings else None,
    }


def slot_budget_for(slot_name: str) -> dict[str, Any]:
    """返回指定 slot 的预算配置；如果没有专门配置，则返回默认预算。"""
    return SLOT_BUDGETS.get(_slot_budget_key(slot_name), DEFAULT_SLOT_BUDGET)


def estimate_tokens(value: str | None) -> int:
    """在不引入 tokenizer 依赖的前提下粗略估算 token 数。"""
    return rough_token_count(value)


def trim_to_token_budget(value: str, max_tokens: int) -> tuple[str, bool]:
    """把文本裁剪到粗略 token 预算以内；这是已有整体预算逻辑，不是第 5.5.1 新压缩算法。"""
    if max_tokens <= 0:
        return "", bool(value)
    if estimate_tokens(value) <= max_tokens:
        return value, False
    max_chars = max(0, max_tokens * 4)
    marker = "\n[TRUNCATED_BY_CONTEXT_BUDGET]"
    if max_chars <= len(marker):
        return marker[:max_chars], True
    return value[: max_chars - len(marker)] + marker, True


@dataclass(frozen=True)
class ContextBudgetReport:
    """整体上下文预算应用结果。"""

    token_budget: int
    original_tokens: int
    injected_tokens: int
    truncated_slots: list[str]
    dropped_slots: list[str]


class ContextBudgetManager:
    """按任务级 token 预算处理上下文 slot。"""

    def __init__(self, budgets: dict[str, int] | None = None):
        self.budgets = {**DEFAULT_CONTEXT_BUDGETS, **(budgets or {})}

    def budget_for(self, task_name: str, override: int | None = None) -> int:
        """获取某个任务的整体 token 预算。"""
        if override is not None:
            return override
        return self.budgets.get(task_name, self.budgets["default"])

    def apply(self, slots: list[BuiltContextSlot], token_budget: int) -> tuple[list[BuiltContextSlot], ContextBudgetReport]:
        """按整体预算处理 slot；本轮新增的是记录预算元数据，不新增压缩策略。"""
        original_tokens = sum(slot.original_tokens for slot in slots)
        remaining = token_budget
        result: list[BuiltContextSlot] = []
        truncated: list[str] = []
        dropped: list[str] = []

        for slot in sorted(slots, key=lambda item: item.priority, reverse=True):
            if remaining <= 0:
                slot.content = ""
                slot.injected_tokens = 0
                slot.was_truncated = True
                slot.truncation_reason = "dropped_by_token_budget"
                self._mark_slot_budget_truncated(slot)
                dropped.append(slot.name)
                result.append(slot)
                continue

            target = min(slot.injected_tokens, remaining)
            content, was_trimmed = trim_to_token_budget(slot.content, target)
            if was_trimmed:
                slot.was_truncated = True
                slot.truncation_reason = "trimmed_by_token_budget"
                self._mark_slot_budget_truncated(slot)
                truncated.append(slot.name)
            slot.content = content
            slot.injected_tokens = estimate_tokens(content)
            remaining -= slot.injected_tokens
            result.append(slot)

        order = {slot.name: index for index, slot in enumerate(slots)}
        ordered = sorted(result, key=lambda item: order[item.name])
        injected_tokens = sum(slot.injected_tokens for slot in ordered)
        return ordered, ContextBudgetReport(token_budget, original_tokens, injected_tokens, truncated, dropped)

    def _mark_slot_budget_truncated(self, slot: BuiltContextSlot) -> None:
        budget_meta = slot.metadata.get("budget_meta")
        if isinstance(budget_meta, dict):
            budget_meta["truncated"] = True


def _slot_budget_key(slot_name: str) -> str:
    return _slot_name_to_text(slot_name).upper()


def _slot_name_to_text(slot_name: Any) -> str:
    value = getattr(slot_name, "value", slot_name)
    return str(value)


def _render_for_budget(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False, sort_keys=True, default=str)


def _is_cjk_char(char: str) -> bool:
    code = ord(char)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
        or 0xF900 <= code <= 0xFAFF
    )
