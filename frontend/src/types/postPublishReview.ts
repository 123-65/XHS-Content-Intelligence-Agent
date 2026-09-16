export type PostPublishReviewStatus = 'WAITING_CONFIRMATION' | 'REVIEWED' | 'DATA_INSUFFICIENT' | 'FAILED'

export interface PostPublishReviewRequest {
  account_id: number
  confirmed: boolean
  review_window?: string
  notes?: string | null
}

export interface PostPublishAction {
  action: string
  label: string
  enabled: boolean
}

export interface StrategyMemoryCandidate {
  type: string
  content: string
  evidence: string
  confidence: 'LOW' | 'MEDIUM' | 'HIGH'
}

export interface PostPublishReviewResponse {
  status: PostPublishReviewStatus
  review_id: number | null
  account_id: number
  published_note_id: number
  package_id: number | null
  summary: string
  metric_summary: Record<string, any>
  target_comparison: Record<string, any>
  conversion_summary: Record<string, any>
  insights: string[]
  data_gaps: Record<string, any>[]
  next_actions: PostPublishAction[]
  strategy_memory_candidates: StrategyMemoryCandidate[]
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
  created_at: string | null
}
