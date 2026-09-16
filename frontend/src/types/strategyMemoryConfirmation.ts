export type StrategyMemoryConfirmationStatus =
  | 'WAITING_CONFIRMATION'
  | 'SAVED'
  | 'DATA_INSUFFICIENT'
  | 'BLOCKED'
  | 'VALIDATION_ERROR'

export type StrategyMemoryType =
  | 'CONTENT_DIRECTION'
  | 'TITLE_STYLE'
  | 'CTA_STYLE'
  | 'AUDIENCE_PAIN_POINT'
  | 'FORMAT_PREFERENCE'
  | 'RISK_AVOIDANCE'
  | 'CONVERSION_SIGNAL'
  | 'DATA_GAP'

export type StrategyMemoryConfidence = 'LOW' | 'MEDIUM' | 'HIGH'

export interface StrategyMemoryCandidate {
  candidate_index: number
  memory_type: StrategyMemoryType
  content: string
  evidence: string
  confidence: StrategyMemoryConfidence
  selected: boolean
}

export interface SelectedStrategyMemoryCandidate {
  candidate_index: number
  memory_type: StrategyMemoryType
  content: string
  evidence: string
  confidence: StrategyMemoryConfidence
}

export interface StrategyMemoryConfirmationRequest {
  account_id: number
  confirmed: boolean
  selected_candidates: SelectedStrategyMemoryCandidate[]
  conversation_id?: number | null
}

export interface StrategyMemoryAction {
  action: string
  label: string
  enabled: boolean
}

export interface StrategyMemoryItem {
  id: number
  account_id: number
  memory_type: string
  status: string
  summary: string
  pattern: string | null
  confidence: string
  source_review_report_id: number | null
  support_count: number
  evidence_count: number
  risk_level: string
  metadata_payload: Record<string, any>
  created_at: string
  updated_at: string
}

export interface StrategyMemoryConfirmationResponse {
  status: StrategyMemoryConfirmationStatus
  account_id: number
  review_id: number
  candidates: StrategyMemoryCandidate[]
  created_memory_ids: number[]
  skipped_duplicates: Record<string, any>[]
  warnings: string[]
  next_actions: StrategyMemoryAction[]
  error_code: string | null
  error_message: string | null
}
