from app.agent.product_entry.schemas import (
    Action,
    AgentChatRequest,
    AgentChatResponse,
    AgentInput,
    AgentPlanningResult,
    AgentResponseStatus,
    AllowedEffect,
    ConfirmationCard,
    ConfirmationRequirement,
    FeedbackAction,
    FeedbackPolarity,
    InputAttachment,
    InputType,
    Intent,
    ParamValidationResult,
    Plan,
    PlanStep,
    PlanValidationResult,
    RiskFlag,
    RouterResult,
    TargetType,
    TrustLevel,
    ValidationIssue,
    ValidationSeverity,
)


CASE_TARGET_AMBIGUOUS = AgentPlanningResult(
    status=AgentResponseStatus.NEED_CLARIFICATION,
    agent_input=AgentInput(user_input="这个不行", input_type=InputType.TEXT),
    router_result=RouterResult(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        confidence=0.72,
        input_type=InputType.TEXT,
        feedback_action=FeedbackAction.REJECT,
        feedback_polarity=FeedbackPolarity.NEGATIVE,
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
        requires_clarification=True,
        clarification_question="你说的“这个”是指当前草稿、标题、选题还是计划？",
    ),
    plan=Plan(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        missing_params=["target_type", "target_id"],
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        summary_for_user="需要先确认你不满意的是哪个对象。",
    ),
    param_validation=ParamValidationResult(
        valid=False,
        missing_params=["target_type", "target_id"],
        issues=[
            ValidationIssue(
                field="target_id",
                message="缺少当前目标，无法判断“这个”指向哪个对象。",
                risk_flag=RiskFlag.TARGET_AMBIGUOUS,
                severity=ValidationSeverity.BLOCKER,
            )
        ],
    ),
    plan_validation=PlanValidationResult(
        valid=False,
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
        blocked_reason="目标不明确，需要追问。",
    ),
    message_to_user="你想否定的是哪个内容？可以告诉我是标题、草稿、选题还是计划。",
)


CASE_REFINE_DRAFT_TITLE = AgentPlanningResult(
    status=AgentResponseStatus.PLANNED,
    agent_input=AgentInput(
        conversation_id="conv_demo",
        account_id=1,
        user_input="这个标题太 AI 了，换自然一点",
        input_type=InputType.TEXT,
        current_target_type=TargetType.DRAFT,
        current_target_id=101,
    ),
    router_result=RouterResult(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        confidence=0.9,
        input_type=InputType.TEXT,
        target_type=TargetType.DRAFT,
        target_id=101,
        feedback_action=FeedbackAction.REFINE,
        feedback_polarity=FeedbackPolarity.NEGATIVE,
        reject_reason="标题太 AI",
        preferred_direction="更自然",
    ),
    plan=Plan(
        plan_id="plan_refine_title_demo",
        conversation_id="conv_demo",
        intent=Intent.REFINE_OR_REJECT_RESULT,
        steps=[
            PlanStep(
                step_no=1,
                action=Action.REFINE_DRAFT,
                description="按用户反馈把草稿标题改得更自然。",
                inputs={"draft_id": 101, "scope": "title", "user_requirement": "标题别太 AI，要更自然"},
                expected_output="更新后的标题候选",
                allowed_effect=AllowedEffect.LOCAL_GENERATION,
            ),
            PlanStep(
                step_no=2,
                action=Action.CREATE_CANDIDATE_MEMORY,
                description="把用户不喜欢“太 AI”标题这件事暂存为候选偏好。",
                inputs={"account_id": 1, "source_type": "user_feedback"},
                depends_on=[1],
                expected_output="候选偏好记忆",
                allowed_effect=AllowedEffect.LOCAL_WRITE,
                requires_confirmation=True,
                risk_flags=[RiskFlag.NEEDS_HUMAN_CONFIRMATION],
            ),
        ],
        required_params=["draft_id"],
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        summary_for_user="可以先重写标题，再询问是否把这个偏好记为长期风格。",
    ),
    param_validation=ParamValidationResult(valid=True, normalized_params={"draft_id": 101, "scope": "title"}),
    plan_validation=PlanValidationResult(
        valid=True,
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        risk_flags=[RiskFlag.NEEDS_HUMAN_CONFIRMATION],
    ),
    message_to_user="我理解你想把当前草稿标题改得更自然。",
)


CASE_NEW_TOPIC_IDEA = AgentPlanningResult(
    status=AgentResponseStatus.PLANNED,
    agent_input=AgentInput(
        account_id=1,
        user_input="我想写一篇 27 届双非本科做 Agent 求职的帖子",
        input_type=InputType.TEXT,
    ),
    router_result=RouterResult(
        intent=Intent.GENERATE_CONTENT_OPPORTUNITY,
        confidence=0.82,
        input_type=InputType.TEXT,
        extracted_params={"topic": "27 届双非本科做 Agent 求职"},
        missing_params=["experiment_id"],
    ),
    plan=Plan(
        intent=Intent.GENERATE_CONTENT_OPPORTUNITY,
        steps=[
            PlanStep(
                step_no=1,
                action=Action.QUERY_ACCOUNT_PROFILE,
                description="先读取账号画像，确认受众和风格边界。",
                inputs={"account_id": 1},
                expected_output="账号画像",
                allowed_effect=AllowedEffect.READ_ONLY,
            ),
            PlanStep(
                step_no=2,
                action=Action.GENERATE_CONTENT_OPPORTUNITY,
                description="把新想法整理成内容机会。",
                inputs={"topic": "27 届双非本科做 Agent 求职"},
                depends_on=[1],
                expected_output="内容机会",
                allowed_effect=AllowedEffect.LOCAL_GENERATION,
            ),
            PlanStep(
                step_no=3,
                action=Action.CREATE_CONTENT_EXPERIMENT,
                description="先形成内容实验，再进入草稿生成。",
                inputs={"account_id": 1},
                depends_on=[2],
                expected_output="候选实验",
                allowed_effect=AllowedEffect.LOCAL_WRITE,
            ),
        ],
        required_params=["account_id", "topic"],
        confirmation_requirement=ConfirmationRequirement.NONE,
        summary_for_user="这个想法应先走内容机会 -> 内容实验 -> 草稿，而不是直接写成文案。",
    ),
    param_validation=ParamValidationResult(valid=True, normalized_params={"topic": "27 届双非本科做 Agent 求职"}),
    plan_validation=PlanValidationResult(valid=True, confirmation_requirement=ConfirmationRequirement.NONE),
    message_to_user="我会先把这个想法整理成内容机会，再设计实验。",
)


CASE_AUTO_PUBLISH_BLOCKED = AgentPlanningResult(
    status=AgentResponseStatus.BLOCKED,
    agent_input=AgentInput(account_id=1, user_input="直接帮我发布到小红书", input_type=InputType.TEXT),
    router_result=RouterResult(
        intent=Intent.UNKNOWN,
        confidence=0.88,
        input_type=InputType.TEXT,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
    ),
    plan=Plan(
        intent=Intent.UNKNOWN,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
        confirmation_requirement=ConfirmationRequirement.BLOCKED,
        blocked_reason="当前阶段不支持自动发布到小红书。",
        summary_for_user="我可以帮你准备发布前检查，但不能自动发布。",
    ),
    param_validation=ParamValidationResult(valid=False),
    plan_validation=PlanValidationResult(
        valid=False,
        confirmation_requirement=ConfirmationRequirement.BLOCKED,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
        blocked_reason="外部写入能力当前被明确阻断。",
    ),
    message_to_user="当前不能自动发布到小红书，我可以生成发布前确认清单。",
)


CASE_IMAGE_ONLY_CLARIFICATION = AgentPlanningResult(
    status=AgentResponseStatus.NEED_CLARIFICATION,
    agent_input=AgentInput(
        input_type=InputType.IMAGE,
        attachments=[
            InputAttachment(
                attachment_id="image_001",
                input_type=InputType.IMAGE,
                name="upload.png",
                mime_type="image/png",
                image_type="UNKNOWN_IMAGE",
                trust_level=TrustLevel.EXTERNAL_UNTRUSTED,
            )
        ],
    ),
    router_result=RouterResult(
        intent=Intent.UNKNOWN,
        confidence=0.2,
        input_type=InputType.IMAGE,
        risk_flags=[RiskFlag.LOW_CONFIDENCE, RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
        requires_clarification=True,
        clarification_question="这张图你希望我分析什么？是笔记截图、评论截图、数据截图还是参考图？",
    ),
    plan=Plan(
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        risk_flags=[RiskFlag.LOW_CONFIDENCE, RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
        summary_for_user="当前阶段不做 OCR 或视觉理解，需要你补充图片用途。",
    ),
    param_validation=ParamValidationResult(valid=False, missing_params=["image_type", "user_intent"]),
    plan_validation=PlanValidationResult(
        valid=False,
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        risk_flags=[RiskFlag.LOW_CONFIDENCE, RiskFlag.UNTRUSTED_EXTERNAL_INPUT],
        blocked_reason="只上传图片时无法判断意图。",
    ),
    message_to_user="请补充一句这张图要用来做什么。",
)


EXAMPLES = {
    "target_ambiguous": CASE_TARGET_AMBIGUOUS,
    "refine_draft_title": CASE_REFINE_DRAFT_TITLE,
    "new_topic_idea": CASE_NEW_TOPIC_IDEA,
    "auto_publish_blocked": CASE_AUTO_PUBLISH_BLOCKED,
    "image_only_clarification": CASE_IMAGE_ONLY_CLARIFICATION,
}


CHAT_CASE_TARGET_AMBIGUOUS = AgentChatResponse(
    session_id="session_demo",
    status=AgentResponseStatus.NEED_CLARIFICATION,
    can_execute=False,
    requires_confirmation=False,
    message="你想修改的是标题、草稿、选题还是计划？",
    next_action="ask_user_to_clarify_target",
    router_result=RouterResult(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        confidence=0.72,
        input_type=InputType.TEXT,
        target_type=TargetType.UNKNOWN,
        feedback_action=FeedbackAction.REJECT,
        feedback_polarity=FeedbackPolarity.NEGATIVE,
        missing_params=["target"],
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
        requires_clarification=True,
        can_execute=False,
        next_action="ask_user_to_clarify_target",
        clarification_question="你说的“这个”是指哪个内容？",
    ),
    plan=Plan(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        missing_params=["target"],
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
        summary_for_user="需要先确认用户要修改的对象。",
        can_execute=False,
        next_action="ask_user_to_clarify_target",
    ),
    confirmation_card=ConfirmationCard(
        title="需要确认修改对象",
        description="你说的“这个”还不明确，请先说明要修改标题、草稿、选题还是计划。",
        action_type="ASK_CLARIFICATION",
        risk_flags=[RiskFlag.TARGET_AMBIGUOUS],
        params_preview={"missing_params": ["target"]},
        confirm_button_text="补充说明",
        cancel_button_text="取消",
        requires_confirmation=True,
        confirmation_requirement=ConfirmationRequirement.CLARIFICATION_REQUIRED,
    ),
)


CHAT_CASE_REFINE_DRAFT_TITLE = AgentChatResponse(
    session_id="session_demo",
    status=AgentResponseStatus.PLANNED,
    can_execute=False,
    requires_confirmation=True,
    message="我理解你想把当前草稿标题改得更自然。",
    next_action="show_confirmation_card",
    router_result=RouterResult(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        confidence=0.9,
        input_type=InputType.TEXT,
        target_type=TargetType.DRAFT,
        target_id=123,
        feedback_action=FeedbackAction.REFINE,
        feedback_polarity=FeedbackPolarity.NEGATIVE,
        reject_reason="标题太 AI",
        preferred_direction="更自然",
        can_execute=False,
    ),
    plan=Plan(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        steps=[
            PlanStep(
                step_no=1,
                action=Action.REFINE_DRAFT,
                description="按用户反馈优化草稿标题。",
                inputs={"draft_id": 123, "scope": "title", "user_requirement": "标题太 AI，换自然一点"},
                expected_output="更自然的标题候选",
                allowed_effect=AllowedEffect.LOCAL_GENERATION,
            )
        ],
        required_params=["draft_id"],
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        summary_for_user="将当前草稿标题改得更自然。",
        can_execute=False,
    ),
    confirmation_card=ConfirmationCard(
        title="确认修改标题",
        description="我会只修改当前草稿的标题方向，不会发布或写入外部平台。",
        action_type=Action.REFINE_DRAFT.value,
        params_preview={"draft_id": 123, "scope": "title"},
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
    ),
)


CHAT_CASE_AUTO_PUBLISH_BLOCKED = AgentChatResponse(
    session_id="session_demo",
    status=AgentResponseStatus.BLOCKED,
    can_execute=False,
    requires_confirmation=False,
    message="当前阶段不支持自动发布到小红书，我可以帮你准备发布前检查清单。",
    next_action="explain_capability_boundary",
    router_result=RouterResult(
        intent=Intent.UNKNOWN,
        confidence=0.88,
        input_type=InputType.TEXT,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
        can_execute=False,
    ),
    plan=Plan(
        intent=Intent.UNKNOWN,
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED, RiskFlag.UNSUPPORTED_ACTION],
        confirmation_requirement=ConfirmationRequirement.BLOCKED,
        blocked_reason="当前阶段不支持自动发布到小红书。",
        can_execute=False,
    ),
    confirmation_card=ConfirmationCard(
        title="当前无法自动发布",
        description="自动发布属于外部写入能力，当前阶段明确阻断。",
        action_type="AUTO_PUBLISH_XHS",
        risk_flags=[RiskFlag.EXTERNAL_WRITE, RiskFlag.CAPABILITY_BOUNDARY_EXCEEDED],
        confirm_button_text="知道了",
        cancel_button_text="关闭",
        requires_confirmation=False,
        confirmation_requirement=ConfirmationRequirement.BLOCKED,
    ),
)


CHAT_EXAMPLE_REQUESTS = {
    "target_ambiguous": AgentChatRequest(text="这个不行", input_type=InputType.TEXT),
    "refine_draft_title": AgentChatRequest(
        text="这个标题太 AI 了，换自然一点",
        input_type=InputType.TEXT,
        current_target_type=TargetType.DRAFT,
        current_target_id=123,
    ),
    "auto_publish_blocked": AgentChatRequest(text="直接帮我发布到小红书", input_type=InputType.TEXT),
}


CHAT_EXAMPLES = {
    "target_ambiguous": CHAT_CASE_TARGET_AMBIGUOUS,
    "refine_draft_title": CHAT_CASE_REFINE_DRAFT_TITLE,
    "auto_publish_blocked": CHAT_CASE_AUTO_PUBLISH_BLOCKED,
}
