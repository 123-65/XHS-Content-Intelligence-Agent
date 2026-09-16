export type DraftReviewStatus = 'WAITING_CONFIRMATION' | 'REVIEWED' | 'PROVIDER_NOT_CONFIGURED' | 'FAILED' | 'BLOCKED'
export type DraftReviewRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface DraftReviewRequest {
  account_id: number
  confirmed: boolean
  review_mode?: string
  check_ai_tone?: boolean
  check_risk?: boolean
  check_evidence_consistency?: boolean
}

export interface DraftReviewIssue {
  field: string
  category: string
  level: DraftReviewRiskLevel
  message: string
  evidence?: string | null
}

export interface DraftReviewResponse {
  status: DraftReviewStatus
  account_id: number
  draft_id: number
  review_report_id: number | null
  can_enter_publish_preparation: boolean
  risk_level: DraftReviewRiskLevel | null
  score: number
  issues: DraftReviewIssue[]
  suggestions: string[]
  warnings: string[]
  summary: string
  block_reasons: string[]
  must_fix_before_publish: string[]
  optional_improvements: string[]
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
}
