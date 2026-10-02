from app.agent.product_entry.schemas import Action, AllowedEffect, ConfirmationRequirement, Intent, RiskFlag, StrictSchema


class ActionCapability(StrictSchema):
    """单个动作的能力声明，本阶段只声明不执行。"""

    action: str
    description: str
    required_params: list[str]
    optional_params: list[str] = []
    allowed_effect: AllowedEffect
    default_confirmation_requirement: ConfirmationRequirement
    supported_in_current_stage: bool
    risk_flags: list[RiskFlag] = []


def _capability(
    action: Action | str,
    description: str,
    required_params: list[str],
    allowed_effect: AllowedEffect,
    default_confirmation_requirement: ConfirmationRequirement = ConfirmationRequirement.NONE,
    supported_in_current_stage: bool = True,
    optional_params: list[str] | None = None,
    risk_flags: list[RiskFlag] | None = None,
) -> ActionCapability:
    """构造动作能力声明。"""
    return ActionCapability(
        action=action.value if isinstance(action, Action) else action,
        description=description,
        required_params=required_params,
        optional_params=optional_params or [],
        allowed_effect=allowed_effect,
        default_confirmation_requirement=default_confirmation_requirement,
        supported_in_current_stage=supported_in_current_stage,
        risk_flags=risk_flags or [],
    )


ACTION_REGISTRY: dict[str, ActionCapability] = {
    Action.ASK_CLARIFICATION.value: _capability(
        Action.ASK_CLARIFICATION,
        "向用户追问缺失信息或消解指代对象。",
        [],
        AllowedEffect.READ_ONLY,
    ),
    Action.QUERY_ACCOUNT_PROFILE.value: _capability(
        Action.QUERY_ACCOUNT_PROFILE,
        "查询账号画像，供后续计划或确认卡片展示。",
        ["account_id"],
        AllowedEffect.READ_ONLY,
    ),
    Action.QUERY_COMPETITOR_EVIDENCE.value: _capability(
        Action.QUERY_COMPETITOR_EVIDENCE,
        "查询竞品报告、内容机会或竞品证据。",
        ["account_id"],
        AllowedEffect.READ_ONLY,
        optional_params=["report_id", "content_opportunity_id"],
    ),
    Action.QUERY_COMMENT_INSIGHT.value: _capability(
        Action.QUERY_COMMENT_INSIGHT,
        "查询评论需求、代表评论和风险信号。",
        ["account_id"],
        AllowedEffect.READ_ONLY,
        optional_params=["report_id", "content_opportunity_id"],
        risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
    ),
    Action.QUERY_STRATEGY_MEMORY.value: _capability(
        Action.QUERY_STRATEGY_MEMORY,
        "查询账号策略记忆。",
        ["account_id"],
        AllowedEffect.READ_ONLY,
    ),
    Action.COLLECT_XHS_NOTES.value: _capability(
        Action.COLLECT_XHS_NOTES,
        "通过已配置的外部小红书采集工具读取用户提供的真实笔记链接，并写入现有业务表。",
        ["account_id", "note_urls"],
        AllowedEffect.EXTERNAL_READ,
        optional_params=["collect_comments", "max_comments", "enable_ocr"],
        risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
    ),
    Action.COLLECT_XHS_ACCOUNTS.value: _capability(
        Action.COLLECT_XHS_ACCOUNTS,
        "通过已配置的外部小红书采集工具读取用户提供的真实同行账号 ID 或主页链接，并写入现有业务表。",
        ["account_id", "competitor_account_ids_or_urls"],
        AllowedEffect.EXTERNAL_READ,
        optional_params=["recent_note_limit"],
        risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
    ),
    Action.ANALYZE_COMPETITOR_DATA.value: _capability(
        Action.ANALYZE_COMPETITOR_DATA,
        "复用现有 CompetitorReportService 基于已入库真实竞品数据生成分析结果。",
        ["account_id"],
        AllowedEffect.EXTERNAL_READ,
        optional_params=["keyword", "limit"],
    ),
    Action.ANALYZE_COMPETITOR.value: _capability(
        Action.ANALYZE_COMPETITOR,
        "基于已采集竞品样本生成竞品分析报告。",
        ["account_id"],
        AllowedEffect.LOCAL_WRITE,
        optional_params=["keyword", "limit"],
    ),
    Action.ANALYZE_VIRAL_NOTE.value: _capability(
        Action.ANALYZE_VIRAL_NOTE,
        "拆解高表现竞品笔记的标题、结构、需求和风险。",
        ["report_id"],
        AllowedEffect.READ_ONLY,
        risk_flags=[RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
    ),
    Action.GENERATE_CONTENT_OPPORTUNITY.value: _capability(
        Action.GENERATE_CONTENT_OPPORTUNITY,
        "基于账号、竞品证据、评论洞察和记忆规划内容机会。",
        ["account_id"],
        AllowedEffect.LOCAL_GENERATION,
        optional_params=["report_id", "topic"],
    ),
    Action.CREATE_CONTENT_EXPERIMENT.value: _capability(
        Action.CREATE_CONTENT_EXPERIMENT,
        "把内容机会转成候选内容实验。",
        ["account_id"],
        AllowedEffect.LOCAL_WRITE,
        optional_params=["report_id", "content_opportunity_id"],
    ),
    Action.GENERATE_DRAFT.value: _capability(
        Action.GENERATE_DRAFT,
        "基于已批准实验生成本地草稿。",
        ["account_id", "experiment_id"],
        AllowedEffect.LOCAL_GENERATION,
        optional_params=["user_requirement"],
    ),
    Action.REVIEW_DRAFT.value: _capability(
        Action.REVIEW_DRAFT,
        "审核本地草稿是否符合账号、实验和风险约束。",
        ["draft_id"],
        AllowedEffect.LOCAL_GENERATION,
    ),
    Action.REFINE_DRAFT.value: _capability(
        Action.REFINE_DRAFT,
        "根据用户反馈局部或整体修改本地草稿。",
        ["draft_id"],
        AllowedEffect.LOCAL_GENERATION,
        optional_params=["scope", "user_requirement"],
    ),
    Action.CREATE_CANDIDATE_MEMORY.value: _capability(
        Action.CREATE_CANDIDATE_MEMORY,
        "把用户反馈或复盘结论暂存为候选记忆。",
        ["account_id"],
        AllowedEffect.LOCAL_WRITE,
        default_confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        optional_params=["source_type", "summary", "evidence"],
        risk_flags=[RiskFlag.NEEDS_HUMAN_CONFIRMATION],
    ),
    Action.QUERY_ANALYTICS.value: _capability(
        Action.QUERY_ANALYTICS,
        "查询已发布内容的公开指标、私域转化和复盘数据。",
        ["account_id"],
        AllowedEffect.READ_ONLY,
        optional_params=["published_note_id", "review_report_id"],
    ),
    Action.NOOP.value: _capability(
        Action.NOOP,
        "不执行任何业务动作，仅返回说明。",
        [],
        AllowedEffect.READ_ONLY,
    ),
}

UNSUPPORTED_ACTION_REGISTRY: dict[str, ActionCapability] = {
    "AUTO_PUBLISH_XHS": _capability(
        "AUTO_PUBLISH_XHS",
        "自动发布到小红书；当前阶段没有平台写入能力，明确阻断。",
        ["account_id", "draft_id"],
        AllowedEffect.EXTERNAL_WRITE,
        default_confirmation_requirement=ConfirmationRequirement.BLOCKED,
        supported_in_current_stage=False,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
    ),
    "AUTO_REPLY_COMMENT": _capability(
        "AUTO_REPLY_COMMENT",
        "自动回复小红书评论；当前阶段没有外部互动写入能力，明确阻断。",
        ["account_id", "comment_id"],
        AllowedEffect.EXTERNAL_WRITE,
        default_confirmation_requirement=ConfirmationRequirement.BLOCKED,
        supported_in_current_stage=False,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
    ),
    "DELETE_NOTE": _capability(
        "DELETE_NOTE",
        "删除外部笔记；属于破坏性动作，当前阶段明确阻断。",
        ["account_id", "note_id"],
        AllowedEffect.DESTRUCTIVE,
        default_confirmation_requirement=ConfirmationRequirement.BLOCKED,
        supported_in_current_stage=False,
        risk_flags=[RiskFlag.DESTRUCTIVE_ACTION, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
    ),
    "MODIFY_EXTERNAL_ACCOUNT": _capability(
        "MODIFY_EXTERNAL_ACCOUNT",
        "修改外部平台账号信息；当前阶段没有外部账号写入能力，明确阻断。",
        ["account_id"],
        AllowedEffect.EXTERNAL_WRITE,
        default_confirmation_requirement=ConfirmationRequirement.BLOCKED,
        supported_in_current_stage=False,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
    ),
}

INTENT_ACTION_MAPPING: dict[Intent, list[Action]] = {
    Intent.GENERATE_CONTENT_OPPORTUNITY: [
        Action.QUERY_ACCOUNT_PROFILE,
        Action.QUERY_COMPETITOR_EVIDENCE,
        Action.QUERY_COMMENT_INSIGHT,
        Action.QUERY_STRATEGY_MEMORY,
        Action.GENERATE_CONTENT_OPPORTUNITY,
    ],
    Intent.GENERATE_DRAFT: [
        Action.QUERY_ACCOUNT_PROFILE,
        Action.QUERY_STRATEGY_MEMORY,
        Action.CREATE_CONTENT_EXPERIMENT,
        Action.GENERATE_DRAFT,
        Action.REVIEW_DRAFT,
    ],
    Intent.REFINE_OR_REJECT_RESULT: [
        Action.REFINE_DRAFT,
        Action.CREATE_CANDIDATE_MEMORY,
    ],
    Intent.ANALYZE_COMPETITOR: [
        Action.QUERY_ACCOUNT_PROFILE,
        Action.COLLECT_XHS_NOTES,
        Action.COLLECT_XHS_ACCOUNTS,
        Action.ANALYZE_COMPETITOR_DATA,
    ],
    Intent.ANALYZE_PUBLISHED_PERFORMANCE: [
        Action.QUERY_ANALYTICS,
        Action.CREATE_CANDIDATE_MEMORY,
    ],
    Intent.QUERY_STATUS: [Action.NOOP],
    Intent.ADD_CONTEXT: [Action.NOOP],
    Intent.CONFIRM_ACTION: [Action.NOOP],
    Intent.CANCEL_ACTION: [Action.NOOP],
    Intent.UNKNOWN: [Action.ASK_CLARIFICATION],
}
