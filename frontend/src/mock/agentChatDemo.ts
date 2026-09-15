import type { AgentChatRequest, AgentChatResponse } from '@/types/agentChat'

export const demoAgentRequest: AgentChatRequest = {
  session_id: 'demo-local-fixture',
  account_id: null,
  text: '我想写一篇 27 届双非本科做 Agent 求职的帖子',
  input_type: 'TEXT',
  attachments: [],
  context: {},
  metadata: { source: 'frontend_local_demo_fixture' }
}

export const demoAgentResponse: AgentChatResponse = {
  session_id: 'demo-local-fixture',
  router_result: {
    intent: 'GENERATE_CONTENT_OPPORTUNITY',
    confidence: 0.9,
    input_type: 'TEXT',
    target_type: 'UNKNOWN',
    target_id: null,
    feedback_action: 'UNKNOWN',
    feedback_polarity: 'UNKNOWN',
    reject_reason: null,
    preferred_direction: null,
    extracted_params: { topic: '27 届双非本科做 Agent 求职' },
    missing_params: [],
    risk_flags: [],
    requires_clarification: false,
    requires_confirmation: false,
    can_execute: true,
    next_action: null,
    error_code: null,
    warning: null,
    clarification_question: null
  },
  plan: {
    plan_id: null,
    conversation_id: null,
    intent: 'GENERATE_CONTENT_OPPORTUNITY',
    steps: [
      {
        step_no: 1,
        action: 'GENERATE_CONTENT_OPPORTUNITY',
        description: '把自然语言想法整理成可评估的内容机会。',
        inputs: {},
        required_params: ['account_id'],
        input_params: { topic: '27 届双非本科做 Agent 求职' },
        depends_on: [],
        expected_output: '内容机会预览',
        allowed_effect: 'LOCAL_GENERATION',
        risk_flags: ['MISSING_REQUIRED_PARAM'],
        requires_confirmation: false,
        can_execute: false
      }
    ],
    required_params: [],
    missing_params: ['account_id', 'step_1.account_id'],
    risk_flags: ['MISSING_REQUIRED_PARAM'],
    confirmation_requirement: 'CLARIFICATION_REQUIRED',
    can_execute: false,
    summary_for_user: '入口预览链路已完成任务规划。',
    blocked_reason: '计划缺少必要参数，需要先补充信息。',
    next_action: 'ask_user_to_provide_required_params',
    metadata: {}
  },
  param_validation: {
    valid: false,
    issues: [
      {
        field: 'step_1.account_id',
        source: 'plan_step',
        message: '缺少必填参数 account_id。',
        suggestion: '请补充 account_id。',
        risk_flag: 'MISSING_REQUIRED_PARAM',
        severity: 'BLOCKER'
      }
    ],
    missing_params: ['step_1.account_id'],
    normalized_params: { step_1: { topic: '27 届双非本科做 Agent 求职' } }
  },
  plan_validation: {
    valid: false,
    confirmation_requirement: 'CLARIFICATION_REQUIRED',
    risk_flags: ['MISSING_REQUIRED_PARAM'],
    issues: [
      {
        field: 'step_1.account_id',
        source: 'plan_step',
        message: '缺少必填参数 account_id。',
        suggestion: '请补充 account_id。',
        risk_flag: 'MISSING_REQUIRED_PARAM',
        severity: 'BLOCKER'
      }
    ],
    blocked_reason: '计划缺少必要参数，需要先补充信息。'
  },
  confirmation_card: {
    title: '需要补充信息',
    description: '缺少必要信息：account_id、step_1.account_id',
    action_type: 'ASK_CLARIFICATION',
    risk_flags: ['MISSING_REQUIRED_PARAM'],
    params_preview: {
      missing_params: ['account_id', 'step_1.account_id'],
      next_action: 'ask_user_to_provide_required_params'
    },
    confirm_button_text: '补充信息',
    cancel_button_text: '取消',
    requires_confirmation: true,
    confirmation_requirement: 'CLARIFICATION_REQUIRED'
  },
  status: 'NEED_CLARIFICATION',
  can_execute: false,
  requires_confirmation: false,
  message: '缺少必要信息：account_id、step_1.account_id',
  next_action: 'ask_user_to_clarify',
  trace_id: 'entry_local_demo_fixture',
  metadata: {
    demo_source: '本地演示数据，未调用接口',
    execution: {
      plan_id: null,
      session_id: null,
      trace_id: null,
      status: 'NEED_CLARIFICATION',
      mode: 'DRY_RUN',
      can_execute: false,
      step_results: [],
      output: {},
      error_code: 'CLARIFICATION_REQUIRED',
      message: '计划需要先补充信息。',
      risk_flags: ['MISSING_REQUIRED_PARAM'],
      confirmation_requirement: 'CLARIFICATION_REQUIRED'
    },
    entry_trace: {
      trace_id: 'entry_local_demo_fixture',
      session_id: 'demo-local-fixture',
      agent_type: 'PRODUCT_ENTRY_AGENT',
      workflow_name: 'router_planner_entry',
      account_id: null,
      input_type: 'TEXT',
      final_status: 'NEED_CLARIFICATION',
      final_intent: 'GENERATE_CONTENT_OPPORTUNITY',
      final_confirmation_requirement: 'CLARIFICATION_REQUIRED',
      final_can_execute: false,
      events: [
        {
          trace_id: 'entry_local_demo_fixture',
          session_id: 'demo-local-fixture',
          stage: 'INPUT_RECEIVED',
          status: null,
          intent: null,
          action: null,
          risk_flags: [],
          missing_params: [],
          confirmation_requirement: null,
          error_code: null,
          warning: null,
          summary: '收到用户输入。',
          payload: { account_id_present: false, text_length: 27 },
          created_at: '2026-09-14T00:00:00Z'
        },
        {
          trace_id: 'entry_local_demo_fixture',
          session_id: 'demo-local-fixture',
          stage: 'ROUTER_VALIDATED',
          status: null,
          intent: 'GENERATE_CONTENT_OPPORTUNITY',
          action: null,
          risk_flags: [],
          missing_params: [],
          confirmation_requirement: null,
          error_code: null,
          warning: null,
          summary: 'RouterResult 已生成并完成校验。',
          payload: { confidence: 0.9, can_execute: true },
          created_at: '2026-09-14T00:00:01Z'
        },
        {
          trace_id: 'entry_local_demo_fixture',
          session_id: 'demo-local-fixture',
          stage: 'PLAN_VALIDATED',
          status: null,
          intent: 'GENERATE_CONTENT_OPPORTUNITY',
          action: null,
          risk_flags: ['MISSING_REQUIRED_PARAM'],
          missing_params: ['account_id', 'step_1.account_id'],
          confirmation_requirement: 'CLARIFICATION_REQUIRED',
          error_code: null,
          warning: '计划缺少必要参数，需要先补充信息。',
          summary: '计划校验完成。',
          payload: { valid: false, issues_count: 1 },
          created_at: '2026-09-14T00:00:02Z'
        }
      ]
    }
  }
}
