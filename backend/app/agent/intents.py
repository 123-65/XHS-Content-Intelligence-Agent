from types import MappingProxyType

from app.agent.schemas.execution import RuntimeAction
from app.agent.schemas.semantic import Intent


BUSINESS_INTENTS = frozenset(
    {
        Intent.RESEARCH,
        Intent.CONTENT_STRATEGY,
        Intent.CONTENT_CREATE,
        Intent.CONTENT_REFINE,
        Intent.POST_PUBLISH_REVIEW,
    }
)

CONTROL_INTENTS = frozenset(
    {
        Intent.QUERY_PROFILE,
        Intent.UPDATE_PROFILE,
        Intent.QUERY_HISTORY,
        Intent.UPDATE_STRATEGY,
        Intent.CANCEL_TASK,
    }
)

INTENT_TO_ALLOWED_RUNTIME_ACTIONS = MappingProxyType(
    {
        Intent.GENERAL_CHAT: frozenset({RuntimeAction.RESPOND}),
        Intent.RESEARCH: frozenset({RuntimeAction.CLARIFY, RuntimeAction.EXECUTE_PLAN}),
        Intent.CONTENT_STRATEGY: frozenset({RuntimeAction.CLARIFY, RuntimeAction.EXECUTE_PLAN}),
        Intent.CONTENT_CREATE: frozenset({RuntimeAction.CLARIFY, RuntimeAction.EXECUTE_PLAN}),
        Intent.CONTENT_REFINE: frozenset({RuntimeAction.CLARIFY, RuntimeAction.EXECUTE_PLAN}),
        Intent.POST_PUBLISH_REVIEW: frozenset({RuntimeAction.CLARIFY, RuntimeAction.EXECUTE_PLAN}),
        Intent.QUERY_PROFILE: frozenset({RuntimeAction.QUERY}),
        Intent.UPDATE_PROFILE: frozenset({RuntimeAction.CONFIRM, RuntimeAction.EXECUTE_CONFIRMED_COMMAND}),
        Intent.QUERY_HISTORY: frozenset({RuntimeAction.QUERY}),
        Intent.UPDATE_STRATEGY: frozenset({RuntimeAction.CONFIRM, RuntimeAction.EXECUTE_CONFIRMED_COMMAND}),
        Intent.CANCEL_TASK: frozenset({RuntimeAction.CANCEL}),
        Intent.UNKNOWN: frozenset({RuntimeAction.CLARIFY}),
    }
)


def validate_runtime_action(intent: Intent, action: RuntimeAction) -> None:
    """拒绝不符合冻结 Intent 交通规则的 Runtime Action。"""
    if action not in INTENT_TO_ALLOWED_RUNTIME_ACTIONS[intent]:
        raise ValueError(f"Runtime Action {action} 不允许用于 Intent {intent}")
