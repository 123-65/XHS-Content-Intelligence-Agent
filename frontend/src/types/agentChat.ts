export type AgentInputType = 'TEXT' | 'IMAGE' | 'URL' | 'FILE' | 'MIXED' | 'UNKNOWN'

export interface AgentChatRequest {
  user_id?: string | null
  account_id?: number | null
  session_id?: string | null
  text?: string | null
  input_type: AgentInputType
  attachments: Record<string, unknown>[]
  context: Record<string, unknown>
  current_target_type?: string | null
  current_target_id?: string | number | null
  metadata?: Record<string, unknown>
}

export interface RouterResult {
  intent: string
  confidence: number
  input_type: string
  target_type: string
  target_id: number | null
  feedback_action: string
  feedback_polarity: string
  reject_reason: string | null
  preferred_direction: string | null
  extracted_params: Record<string, unknown>
  missing_params: string[]
  risk_flags: string[]
  requires_clarification: boolean
  requires_confirmation: boolean
  can_execute: boolean
  next_action: string | null
  error_code: string | null
  warning: string | null
  clarification_question: string | null
}

export interface PlanStep {
  step_no: number
  action: string
  description: string
  inputs: Record<string, unknown>
  required_params: string[]
  input_params: Record<string, unknown>
  depends_on: number[]
  expected_output: string | null
  allowed_effect: string
  risk_flags: string[]
  requires_confirmation: boolean
  can_execute: boolean
}

export interface Plan {
  plan_id: string | null
  conversation_id: string | null
  intent: string
  steps: PlanStep[]
  required_params: string[]
  missing_params: string[]
  risk_flags: string[]
  confirmation_requirement: string
  can_execute: boolean
  summary_for_user: string | null
  blocked_reason: string | null
  next_action: string | null
  metadata: Record<string, unknown>
}

export interface ValidationIssue {
  field: string | null
  source: string | null
  message: string
  suggestion: string | null
  risk_flag: string | null
  severity: string
}

export interface ParamValidationResult {
  valid: boolean
  issues: ValidationIssue[]
  missing_params: string[]
  normalized_params: Record<string, unknown>
}

export interface PlanValidationResult {
  valid: boolean
  confirmation_requirement: string
  risk_flags: string[]
  issues: ValidationIssue[]
  blocked_reason: string | null
}

export interface ConfirmationCard {
  title: string
  description: string
  action_type: string
  risk_flags: string[]
  params_preview: Record<string, unknown>
  confirm_button_text: string
  cancel_button_text: string
  requires_confirmation: boolean
  confirmation_requirement: string
}

export interface EntryTraceEvent {
  trace_id: string
  session_id: string | null
  stage: string
  status: string | null
  intent: string | null
  action: string | null
  risk_flags: string[]
  missing_params: string[]
  confirmation_requirement: string | null
  error_code: string | null
  warning: string | null
  summary: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface EntryTrace {
  trace_id: string
  session_id: string | null
  agent_type: string
  workflow_name: string
  account_id: number | null
  input_type: string
  final_status: string | null
  final_intent: string | null
  final_confirmation_requirement: string | null
  final_can_execute: boolean
  events: EntryTraceEvent[]
}

export interface AgentExecutionResult {
  plan_id: string | null
  session_id: string | null
  trace_id: string | null
  status: string
  mode: string
  can_execute: boolean
  step_results: Record<string, unknown>[]
  output: Record<string, unknown>
  error_code: string | null
  message: string | null
  risk_flags: string[]
  confirmation_requirement: string | null
}

export interface AgentChatResponse {
  session_id: string | null
  router_result: RouterResult | null
  plan: Plan | null
  param_validation: ParamValidationResult | null
  plan_validation: PlanValidationResult | null
  confirmation_card: ConfirmationCard | null
  status: string
  can_execute: boolean
  requires_confirmation: boolean
  message: string
  next_action: string | null
  trace_id: string | null
  metadata: {
    execution?: AgentExecutionResult
    entry_trace?: EntryTrace
    demo_source?: string
    [key: string]: unknown
  }
}
