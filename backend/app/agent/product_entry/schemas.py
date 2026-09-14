from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    """产品入口层 Schema 基类，禁止未声明字段进入 Trace。"""

    model_config = ConfigDict(extra="forbid")


class InputType(StrEnum):
    """用户输入类型。"""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    URL = "URL"
    FILE = "FILE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class Intent(StrEnum):
    """Router 识别的用户意图。"""

    GENERATE_CONTENT_OPPORTUNITY = "GENERATE_CONTENT_OPPORTUNITY"
    GENERATE_DRAFT = "GENERATE_DRAFT"
    REFINE_OR_REJECT_RESULT = "REFINE_OR_REJECT_RESULT"
    ANALYZE_COMPETITOR = "ANALYZE_COMPETITOR"
    ANALYZE_PUBLISHED_PERFORMANCE = "ANALYZE_PUBLISHED_PERFORMANCE"
    QUERY_STATUS = "QUERY_STATUS"
    ADD_CONTEXT = "ADD_CONTEXT"
    CONFIRM_ACTION = "CONFIRM_ACTION"
    CANCEL_ACTION = "CANCEL_ACTION"
    UNKNOWN = "UNKNOWN"


class TargetType(StrEnum):
    """用户反馈或动作指向的对象。"""

    ACCOUNT = "ACCOUNT"
    COMPETITOR_ACCOUNT = "COMPETITOR_ACCOUNT"
    COMPETITOR_NOTE = "COMPETITOR_NOTE"
    COMMENT = "COMMENT"
    CONTENT_OPPORTUNITY = "CONTENT_OPPORTUNITY"
    CONTENT_EXPERIMENT = "CONTENT_EXPERIMENT"
    DRAFT = "DRAFT"
    PLAN = "PLAN"
    MEMORY = "MEMORY"
    UNKNOWN = "UNKNOWN"


class FeedbackAction(StrEnum):
    """用户反馈动作。"""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REFINE = "REFINE"
    REGENERATE = "REGENERATE"
    ADD_CONSTRAINT = "ADD_CONSTRAINT"
    CLARIFY = "CLARIFY"
    UNKNOWN = "UNKNOWN"


class FeedbackPolarity(StrEnum):
    """用户反馈倾向。"""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class TrustLevel(StrEnum):
    """输入或上下文的可信等级。"""

    SYSTEM_TRUSTED = "SYSTEM_TRUSTED"
    USER_TRUSTED = "USER_TRUSTED"
    INTERNAL_DATA = "INTERNAL_DATA"
    EXTERNAL_UNTRUSTED = "EXTERNAL_UNTRUSTED"
    MOCK_DATA = "MOCK_DATA"
    UNKNOWN = "UNKNOWN"


class Action(StrEnum):
    """Planner 当前允许描述的动作。"""

    ASK_CLARIFICATION = "ASK_CLARIFICATION"
    QUERY_ACCOUNT_PROFILE = "QUERY_ACCOUNT_PROFILE"
    QUERY_COMPETITOR_EVIDENCE = "QUERY_COMPETITOR_EVIDENCE"
    QUERY_COMMENT_INSIGHT = "QUERY_COMMENT_INSIGHT"
    QUERY_STRATEGY_MEMORY = "QUERY_STRATEGY_MEMORY"
    ANALYZE_COMPETITOR = "ANALYZE_COMPETITOR"
    ANALYZE_VIRAL_NOTE = "ANALYZE_VIRAL_NOTE"
    GENERATE_CONTENT_OPPORTUNITY = "GENERATE_CONTENT_OPPORTUNITY"
    CREATE_CONTENT_EXPERIMENT = "CREATE_CONTENT_EXPERIMENT"
    GENERATE_DRAFT = "GENERATE_DRAFT"
    REVIEW_DRAFT = "REVIEW_DRAFT"
    REFINE_DRAFT = "REFINE_DRAFT"
    CREATE_CANDIDATE_MEMORY = "CREATE_CANDIDATE_MEMORY"
    QUERY_ANALYTICS = "QUERY_ANALYTICS"
    NOOP = "NOOP"


class AllowedEffect(StrEnum):
    """动作影响范围。"""

    READ_ONLY = "READ_ONLY"
    LOCAL_GENERATION = "LOCAL_GENERATION"
    LOCAL_WRITE = "LOCAL_WRITE"
    EXTERNAL_READ = "EXTERNAL_READ"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class RiskFlag(StrEnum):
    """Router / Planner / Validator 可标记的风险。"""

    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MISSING_REQUIRED_PARAM = "MISSING_REQUIRED_PARAM"
    TARGET_AMBIGUOUS = "TARGET_AMBIGUOUS"
    UNTRUSTED_EXTERNAL_INPUT = "UNTRUSTED_EXTERNAL_INPUT"
    MOCK_DATA_USED = "MOCK_DATA_USED"
    UNSUPPORTED_ACTION = "UNSUPPORTED_ACTION"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    DESTRUCTIVE_ACTION = "DESTRUCTIVE_ACTION"
    NEEDS_HUMAN_CONFIRMATION = "NEEDS_HUMAN_CONFIRMATION"
    PROMPT_INJECTION_RISK = "PROMPT_INJECTION_RISK"
    CAPABILITY_BOUNDARY_EXCEEDED = "CAPABILITY_BOUNDARY_EXCEEDED"


class ConfirmationRequirement(StrEnum):
    """执行前的澄清或确认要求。"""

    NONE = "NONE"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    USER_CONFIRM_REQUIRED = "USER_CONFIRM_REQUIRED"
    BLOCKED = "BLOCKED"


class AgentResponseStatus(StrEnum):
    """产品入口层响应状态。"""

    ROUTED = "ROUTED"
    PLANNED = "PLANNED"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    READY_TO_EXECUTE = "READY_TO_EXECUTE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ValidationSeverity(StrEnum):
    """参数或计划校验问题等级。"""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKER = "BLOCKER"


class InputAttachment(StrictSchema):
    """用户上传的图片、链接或文件。"""

    attachment_id: str | None = Field(default=None, description="附件稳定 ID，可由前端或文件系统生成")
    input_type: InputType = Field(default=InputType.UNKNOWN, description="附件输入类型")
    name: str | None = Field(default=None, description="附件名称")
    url: str | None = Field(default=None, description="附件 URL 或引用地址")
    mime_type: str | None = Field(default=None, description="MIME 类型")
    image_type: str | None = Field(default=None, description="图片类型预留，如 XHS_NOTE_SCREENSHOT")
    trust_level: TrustLevel = Field(default=TrustLevel.UNKNOWN, description="附件可信等级")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附件扩展元数据")


class AgentInput(StrictSchema):
    """一次用户输入。"""

    conversation_id: str | None = Field(default=None, description="会话 ID，可为空")
    account_id: int | None = Field(default=None, description="当前账号 ID，可为空")
    user_input: str | None = Field(default=None, description="用户输入文本")
    input_type: InputType = Field(default=InputType.UNKNOWN, description="本轮输入类型")
    attachments: list[InputAttachment] = Field(default_factory=list, description="本轮附件列表")
    current_target_type: TargetType = Field(default=TargetType.UNKNOWN, description="当前交互对象类型")
    current_target_id: int | None = Field(default=None, description="当前交互对象 ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="入口层扩展元数据")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="用户输入创建时间")


class AgentChatRequest(StrictSchema):
    """前端自由输入框提交的一次请求。"""

    user_id: str | None = Field(default=None, description="用户 ID，可为空")
    account_id: int | None = Field(default=None, description="账号 ID，可为空，入口层不能编造")
    session_id: str | None = Field(default=None, description="会话 ID，可为空")
    text: str | None = Field(default=None, description="用户输入文本，可为空")
    input_type: InputType = Field(default=InputType.TEXT, description="输入类型")
    attachments: list[InputAttachment] = Field(default_factory=list, description="附件列表")
    context: dict[str, Any] = Field(default_factory=dict, description="前端传入的轻量上下文")
    current_target_type: TargetType | None = Field(default=None, description="当前交互对象类型")
    current_target_id: str | int | None = Field(default=None, description="当前交互对象 ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="请求扩展元数据")


class RouterResult(StrictSchema):
    """Router 对用户输入的结构化理解。"""

    intent: Intent = Field(default=Intent.UNKNOWN, description="识别出的用户意图")
    confidence: float = Field(default=0, ge=0, le=1, description="意图识别置信度")
    input_type: InputType = Field(default=InputType.UNKNOWN, description="识别出的输入类型")
    target_type: TargetType = Field(default=TargetType.UNKNOWN, description="反馈或动作目标类型")
    target_id: int | None = Field(default=None, description="反馈或动作目标 ID，Router 不允许编造")
    feedback_action: FeedbackAction = Field(default=FeedbackAction.UNKNOWN, description="用户反馈动作")
    feedback_polarity: FeedbackPolarity = Field(default=FeedbackPolarity.UNKNOWN, description="用户反馈倾向")
    reject_reason: str | None = Field(default=None, description="拒绝或不满意原因")
    preferred_direction: str | None = Field(default=None, description="用户偏好的修改方向")
    extracted_params: dict[str, Any] = Field(default_factory=dict, description="从输入中抽取的参数")
    missing_params: list[str] = Field(default_factory=list, description="缺失参数")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="路由阶段风险标记")
    requires_clarification: bool = Field(default=False, description="是否需要追问澄清")
    requires_confirmation: bool = Field(default=False, description="是否需要用户确认后才能继续")
    can_execute: bool = Field(default=False, description="是否可直接进入执行，默认安全关闭")
    next_action: str | None = Field(default=None, description="下一步建议动作")
    error_code: str | None = Field(default=None, description="Router 阶段错误码，正常路由时为空")
    warning: str | None = Field(default=None, description="Router 阶段面向 Trace 或用户的警告说明")
    clarification_question: str | None = Field(default=None, description="给用户的澄清问题")


class PlanStep(StrictSchema):
    """Planner 生成的单个计划步骤，只描述不执行。"""

    step_no: int = Field(ge=1, description="步骤序号，从 1 开始")
    action: Action = Field(description="计划动作")
    description: str = Field(description="面向用户或 Trace 的步骤说明")
    inputs: dict[str, Any] = Field(default_factory=dict, description="本步骤需要的输入")
    depends_on: list[int] = Field(default_factory=list, description="依赖的步骤序号")
    expected_output: str | None = Field(default=None, description="预期输出")
    allowed_effect: AllowedEffect = Field(description="动作影响范围")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="步骤风险标记")
    requires_confirmation: bool = Field(default=False, description="该步骤执行前是否需要用户确认")
    can_execute: bool = Field(default=False, description="该步骤是否可直接执行，默认安全关闭")


class Plan(StrictSchema):
    """完整任务计划。"""

    plan_id: str | None = Field(default=None, description="计划 ID，可在后续 Trace 层生成")
    conversation_id: str | None = Field(default=None, description="会话 ID")
    intent: Intent = Field(default=Intent.UNKNOWN, description="计划对应意图")
    steps: list[PlanStep] = Field(default_factory=list, description="计划步骤")
    required_params: list[str] = Field(default_factory=list, description="计划要求的参数")
    missing_params: list[str] = Field(default_factory=list, description="仍然缺失的参数")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="计划级风险标记")
    confirmation_requirement: ConfirmationRequirement = Field(default=ConfirmationRequirement.NONE, description="计划级确认要求")
    can_execute: bool = Field(default=False, description="计划是否可直接进入执行，默认安全关闭")
    summary_for_user: str | None = Field(default=None, description="前端确认卡片摘要")
    blocked_reason: str | None = Field(default=None, description="阻断原因")
    next_action: str | None = Field(default=None, description="下一步建议动作")
    metadata: dict[str, Any] = Field(default_factory=dict, description="计划扩展元数据")


class ValidationIssue(StrictSchema):
    """参数或计划校验问题。"""

    field: str | None = Field(default=None, description="问题字段")
    message: str = Field(description="问题说明")
    risk_flag: RiskFlag | None = Field(default=None, description="关联风险标记")
    severity: ValidationSeverity = Field(default=ValidationSeverity.ERROR, description="问题等级")


class ParamValidationResult(StrictSchema):
    """参数校验结果。"""

    valid: bool = Field(description="参数是否有效")
    issues: list[ValidationIssue] = Field(default_factory=list, description="参数问题列表")
    missing_params: list[str] = Field(default_factory=list, description="缺失参数")
    normalized_params: dict[str, Any] = Field(default_factory=dict, description="规范化后的参数")


class PlanValidationResult(StrictSchema):
    """计划校验结果。"""

    valid: bool = Field(description="计划是否可进入执行阶段")
    confirmation_requirement: ConfirmationRequirement = Field(description="校验后的确认要求")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="校验阶段风险标记")
    issues: list[ValidationIssue] = Field(default_factory=list, description="计划问题列表")
    blocked_reason: str | None = Field(default=None, description="阻断原因")


class AgentPlanningResult(StrictSchema):
    """6.1 聚合输出结构，仅定义协议，不执行计划。"""

    status: AgentResponseStatus = Field(description="入口层处理状态")
    agent_input: AgentInput = Field(description="原始用户输入结构")
    router_result: RouterResult | None = Field(default=None, description="Router 结构化结果")
    plan: Plan | None = Field(default=None, description="Planner 结构化计划")
    param_validation: ParamValidationResult | None = Field(default=None, description="参数校验结果")
    plan_validation: PlanValidationResult | None = Field(default=None, description="计划校验结果")
    message_to_user: str | None = Field(default=None, description="返回给用户的说明")


class ConfirmationCard(StrictSchema):
    """前端确认、澄清或阻断卡片。"""

    title: str = Field(description="卡片标题")
    description: str = Field(description="卡片说明")
    action_type: str = Field(description="卡片代表的动作类型")
    risk_flags: list[RiskFlag] = Field(default_factory=list, description="风险标记")
    params_preview: dict[str, Any] = Field(default_factory=dict, description="参数预览")
    confirm_button_text: str = Field(default="确认执行", description="确认按钮文案")
    cancel_button_text: str = Field(default="取消", description="取消按钮文案")
    requires_confirmation: bool = Field(default=True, description="是否需要用户交互确认")
    confirmation_requirement: ConfirmationRequirement = Field(description="确认、澄清或阻断要求")


class AgentChatResponse(StrictSchema):
    """Agent 产品入口层统一响应。"""

    session_id: str | None = Field(default=None, description="会话 ID")
    router_result: RouterResult | None = Field(default=None, description="Router 结构化结果")
    plan: Plan | None = Field(default=None, description="Planner 结构化计划")
    param_validation: ParamValidationResult | None = Field(default=None, description="参数校验结果")
    plan_validation: PlanValidationResult | None = Field(default=None, description="计划校验结果")
    confirmation_card: ConfirmationCard | None = Field(default=None, description="前端确认卡片")
    status: AgentResponseStatus = Field(description="入口层响应状态")
    can_execute: bool = Field(default=False, description="是否可执行，默认安全关闭")
    requires_confirmation: bool = Field(default=False, description="是否需要确认")
    message: str = Field(description="返回给用户的说明")
    next_action: str | None = Field(default=None, description="下一步建议动作")
    trace_id: str | None = Field(default=None, description="后续 Trace ID 预留")
    metadata: dict[str, Any] = Field(default_factory=dict, description="响应扩展元数据")
