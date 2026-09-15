export type DraftContextPreviewStatus = 'READY' | 'PARTIAL' | 'DATA_INSUFFICIENT' | 'BLOCKED' | 'FAILED'

export interface DraftContextPreviewRequest {
  account_id: number
  user_requirements?: string | null
  include_strategy_memory?: boolean
  include_comments?: boolean
}

export interface DraftContextPreviewResponse {
  status: DraftContextPreviewStatus
  account_id: number
  experiment_id: number
  ready_for_draft_generation: boolean
  requires_confirmation: boolean
  context: Record<string, any>
  missing_context: Array<Record<string, any>>
  warnings: string[]
  confirmation: Record<string, any>
  next_actions: Array<Record<string, any>>
  error_code: string | null
  error_message: string | null
}
