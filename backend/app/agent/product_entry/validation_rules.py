from app.agent.product_entry.schemas import Action, ParamSpec, ParamType


def _spec(
    name: str,
    param_type: ParamType = ParamType.ANY,
    required: bool = True,
    allowed_sources: list[str] | None = None,
    allow_untrusted: bool = False,
    description: str | None = None,
) -> ParamSpec:
    """构造动作参数规格。"""
    return ParamSpec(
        name=name,
        param_type=param_type,
        required=required,
        allowed_sources=allowed_sources or ["agent_input", "router_result", "plan_step", "conversation_state", "user_context", "internal_data"],
        allow_untrusted=allow_untrusted,
        description=description,
    )


ACTION_PARAM_SPECS: dict[Action, list[ParamSpec]] = {
    Action.ASK_CLARIFICATION: [
        _spec("question", ParamType.TEXT),
    ],
    Action.QUERY_ACCOUNT_PROFILE: [
        _spec("account_id", ParamType.ID),
    ],
    Action.QUERY_COMPETITOR_EVIDENCE: [
        _spec("account_id", ParamType.ID),
    ],
    Action.QUERY_COMMENT_INSIGHT: [
        _spec("account_id", ParamType.ID),
    ],
    Action.QUERY_STRATEGY_MEMORY: [
        _spec("account_id", ParamType.ID),
    ],
    Action.COLLECT_XHS_NOTES: [
        _spec("account_id", ParamType.ID),
        _spec("note_urls", ParamType.LIST, allow_untrusted=True),
        _spec("collect_comments", ParamType.BOOL, required=False),
        _spec("max_comments", ParamType.INT, required=False),
        _spec("enable_ocr", ParamType.BOOL, required=False),
    ],
    Action.COLLECT_XHS_ACCOUNTS: [
        _spec("account_id", ParamType.ID),
        _spec("competitor_account_ids_or_urls", ParamType.LIST, allow_untrusted=True),
        _spec("recent_note_limit", ParamType.INT, required=False),
    ],
    Action.ANALYZE_COMPETITOR_DATA: [
        _spec("account_id", ParamType.ID),
        _spec("keyword", ParamType.TEXT, required=False, allow_untrusted=True),
        _spec("limit", ParamType.INT, required=False),
    ],
    Action.ANALYZE_COMPETITOR: [
        _spec("account_id", ParamType.ID),
        _spec("competitor_account_id", ParamType.ID, required=False),
        _spec("competitor_note_id", ParamType.ID, required=False),
        _spec("note_snapshot_id", ParamType.ID, required=False),
    ],
    Action.ANALYZE_VIRAL_NOTE: [
        _spec("account_id", ParamType.ID),
        _spec("competitor_note_id", ParamType.ID, required=False),
        _spec("note_snapshot_id", ParamType.ID, required=False),
    ],
    Action.GENERATE_CONTENT_OPPORTUNITY: [
        _spec("account_id", ParamType.ID),
        _spec("topic", ParamType.TEXT, required=False, allow_untrusted=True),
        _spec("audience", ParamType.TEXT, required=False),
        _spec("user_goal", ParamType.TEXT, required=False),
        _spec("reference_url", ParamType.URL, required=False, allow_untrusted=True),
    ],
    Action.CREATE_CONTENT_EXPERIMENT: [
        _spec("account_id", ParamType.ID),
        _spec("content_opportunity_id", ParamType.ID, required=False),
        _spec("topic", ParamType.TEXT, required=False, allow_untrusted=True),
        _spec("angle", ParamType.TEXT, required=False),
        _spec("target_audience", ParamType.TEXT, required=False),
    ],
    Action.GENERATE_DRAFT: [
        _spec("account_id", ParamType.ID),
        _spec("experiment_id", ParamType.ID, required=False),
        _spec("topic", ParamType.TEXT, required=False, allow_untrusted=True),
        _spec("angle", ParamType.TEXT, required=False),
        _spec("target_audience", ParamType.TEXT, required=False),
    ],
    Action.REVIEW_DRAFT: [
        _spec("account_id", ParamType.ID),
        _spec("draft_id", ParamType.ID, required=False),
        _spec("draft_text", ParamType.TEXT, required=False),
    ],
    Action.REFINE_DRAFT: [
        _spec("account_id", ParamType.ID),
        _spec("draft_id", ParamType.ID, required=False),
        _spec("draft_text", ParamType.TEXT, required=False),
        _spec("feedback", ParamType.TEXT),
    ],
    Action.CREATE_CANDIDATE_MEMORY: [
        _spec("account_id", ParamType.ID),
        _spec("memory_content", ParamType.TEXT),
        _spec("source", ParamType.STRING),
    ],
    Action.QUERY_ANALYTICS: [
        _spec("account_id", ParamType.ID),
        _spec("draft_id", ParamType.ID, required=False),
        _spec("note_id", ParamType.ID, required=False),
        _spec("analytics_snapshot_id", ParamType.ID, required=False),
    ],
    Action.NOOP: [],
}


ACTION_ALTERNATIVE_PARAM_GROUPS: dict[Action, list[list[str]]] = {
    Action.REVIEW_DRAFT: [["draft_id", "draft_text"]],
    Action.REFINE_DRAFT: [["draft_id", "draft_text"]],
}
