export interface DeveloperAgentRunSummary {
  id: number
  account_id: number | null
  workflow_name: string
  agent_type: string
  status: string
  stop_reason: string | null
  total_steps: number
  success_steps: number
  failed_steps: number
  llm_call_count: number
  total_latency_ms: number
  total_token_count: number
  estimated_cost: string | number
  started_at: string
  finished_at: string | null
}

export interface DeveloperAgentStepTrace {
  id: number
  run_id: number
  step_order: number
  step_name: string
  tool_name: string
  tool_input_summary: Record<string, unknown>
  tool_output_summary: Record<string, unknown>
  provider_name: string | null
  is_mock: boolean
  prompt_key: string | null
  prompt_version: string | null
  latency_ms: number
  token_count: number
  estimated_cost: string | number
  fallback_used: boolean
  status: string
  error_code: string | null
  error_message: string | null
  llm_calls: Record<string, unknown>[]
  tool_calls: Record<string, unknown>[]
}

export interface DeveloperAgentRunDetail extends DeveloperAgentRunSummary {
  steps: DeveloperAgentStepTrace[]
  tool_calls: Record<string, unknown>[]
  llm_calls: Record<string, unknown>[]
  fallback_records: Record<string, unknown>[]
  errors: Record<string, unknown>[]
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

