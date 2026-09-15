from typing import Any

from sqlalchemy.orm import Session

from app.agent.product_entry.executor import ActionHandlerRegistry
from app.agent.product_entry.schemas import Action, PlanStep
from app.services.account_sev import AccountProfileService


def query_account_profile_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """查询账号画像，只读复用现有 AccountProfileService。"""
    account_id = _account_id(step, context)
    service = _account_service(context)
    account = service.get_account(account_id)

    summary_parts = [
        f"账号定位：{account.positioning}",
        f"目标用户：{account.target_audience}",
    ]
    if account.content_domain:
        summary_parts.append(f"内容领域：{account.content_domain}")
    if account.tone_preference:
        summary_parts.append(f"语气偏好：{account.tone_preference}")

    return {
        "account_id": account.id,
        "account_name": account.account_name,
        "platform": account.platform,
        "content_domain": account.content_domain,
        "positioning": account.positioning,
        "target_audience": account.target_audience,
        "persona": account.persona,
        "tone_preference": account.tone_preference,
        "risk_preference": account.risk_preference,
        "account_stage": account.account_stage,
        "primary_goal": account.primary_goal,
        "summary": "；".join(summary_parts),
    }


def build_readonly_action_handler_registry(db: Session) -> ActionHandlerRegistry:
    """构建只读 REAL 执行白名单，只注册 QUERY_ACCOUNT_PROFILE。"""
    registry = ActionHandlerRegistry()
    registry.register(Action.QUERY_ACCOUNT_PROFILE, query_account_profile_handler)
    return registry


def _account_id(step: PlanStep, context: dict[str, Any]) -> int:
    value = step.input_params.get("account_id") or step.inputs.get("account_id") or context.get("account_id")
    if value is None:
        raise ValueError("account_id is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("account_id must be an integer") from exc


def _account_service(context: dict[str, Any]) -> AccountProfileService:
    service = context.get("account_service")
    if isinstance(service, AccountProfileService):
        return service
    db = context.get("db")
    if db is None:
        raise ValueError("db session is required")
    return AccountProfileService(db)
