export type AgentInputType = 'TEXT' | 'IMAGE' | 'URL' | 'FILE' | 'MIXED' | 'UNKNOWN'

export interface AgentChatRequest {
  user_id?: string | null
  account_id?: number | null
  conversation_id?: number | null
  session_id?: string | null
  text?: string | null
  input_type: AgentInputType
  attachments: Record<string, unknown>[] | Record<string, unknown>
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

export interface AccountProfileBusinessResult {
  account_id: number
  account_name: string
  platform: string
  content_domain: string | null
  positioning: string
  target_audience: string
  persona: string | null
  tone_preference: string | null
  risk_preference: string
  account_stage: string
  primary_goal: string
  summary: string
}

export interface CompetitorEvidenceItem {
  source_type?: string
  opportunity_id?: number
  report_id?: number
  title?: string
  summary?: string
  content_pillar?: string
  target_audience?: string
  comment_demand_type?: string
  confidence?: number
  risk_level?: string
}

export interface CompetitorEvidenceBusinessResult {
  items: CompetitorEvidenceItem[]
  total: number
  data_status?: string
  summary: string
}

export interface CommentInsightSummaryItem {
  type?: string
  name?: string
  count?: number
}

export interface RepresentativeComment {
  untrusted_text: string
  like_count?: number
  source?: string
  source_type?: string
  demand_type?: string
}

export interface CommentInsightBusinessResult {
  demand_summary: CommentInsightSummaryItem[]
  representative_comments: RepresentativeComment[]
  conversion_signal_summary: CommentInsightSummaryItem[]
  risk_summary: CommentInsightSummaryItem[]
  data_status: string
  summary: string
}

export interface StrategyMemoryItem {
  memory_id?: number
  memory_type?: string
  status?: string
  summary?: string
  pattern?: string
  confidence?: number
  support_count?: number
  risk_level?: string
}

export interface StrategyMemoryBusinessResult {
  items: StrategyMemoryItem[]
  total: number
  data_status?: string
  summary: string
}

export interface DraftContextSlotPreview {
  name: string
  priority: number
  token_limit?: number | null
  estimated_tokens: number
  source_type: string
  trust_level: string
  data_status: string
  item_count: number
  preview: string
  untrusted_warning?: string | null
}

export interface DraftContextPreviewBusinessResult {
  account_id: number
  experiment_id: number
  can_generate_draft: boolean
  block_reason: string | null
  slot_count: number
  total_token_budget: number
  total_estimated_tokens?: number
  slots: DraftContextSlotPreview[]
  missing_slots: string[]
  risk_flags: string[]
  summary: string
  truncation_summary?: Record<string, unknown>
  sanitizer_summary?: Record<string, unknown>
}

export interface ReadonlyBusinessResult {
  account_id?: number
  account_name?: string
  platform?: string
  content_domain?: string | null
  positioning?: string
  target_audience?: string
  persona?: string | null
  tone_preference?: string | null
  risk_preference?: string
  account_stage?: string
  primary_goal?: string
  summary?: string
  account_profile?: AccountProfileBusinessResult
  competitor_evidence?: CompetitorEvidenceBusinessResult
  comment_insight?: CommentInsightBusinessResult
  strategy_memory?: StrategyMemoryBusinessResult
  draft_context_preview?: DraftContextPreviewBusinessResult
  xhs_notes_collection?: Record<string, unknown>
  xhs_accounts_collection?: Record<string, unknown>
  competitor_analysis?: Record<string, unknown>
}

export interface WorkflowTimelineItem {
  step_order: number
  action: string
  status: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  input_summary: string | null
  output_summary: string | null
  data_count: Record<string, number>
  evidence_ids: Record<string, unknown>
  warnings: string[]
  error_code: string | null
  error_message: string | null
}

export interface AgentChatResponse {
  session_id: string | null
  conversation_id: number | null
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
    business_result?: ReadonlyBusinessResult | null
    entry_trace?: EntryTrace
    workflow_timeline?: WorkflowTimelineItem[]
    demo_source?: string
    [key: string]: unknown
  }
}

export interface ConversationCurrentState {
  current_goal: string | null
  active_account_id: number | null
  active_opportunity_id: number | null
  active_experiment_id: number | null
  active_draft_id: number | null
  current_target_type: string | null
  current_target_id: string | number | null
  last_action: string | null
  last_artifacts: Record<string, unknown>[]
  pending_confirmation: Record<string, unknown> | null
  conversation_constraints: Record<string, unknown>
}

export interface ConversationResponse {
  id: number
  account_id: number | null
  title: string
  status: string
  current_state: ConversationCurrentState
  created_at: string
  updated_at: string
  last_message_at: string | null
}

export interface ConversationMessageResponse {
  id: number
  conversation_id: number
  role: string
  content: string
  message_type: string
  metadata_payload: Record<string, unknown>
  trace_id: string | null
  created_at: string
}
