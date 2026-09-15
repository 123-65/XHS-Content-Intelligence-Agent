export type OperationRunStatus = 'SUCCESS' | 'PARTIAL' | 'DATA_INSUFFICIENT' | 'FAILED'

export interface OperationRunCreate {
  account_id: number
  evidence_refresh_run_id?: number | null
  data_refresh_run_id?: number | null
  analysis_date?: string | null
}

export interface OperationRecommendation {
  rank: number
  title: string
  reason: string
  evidence: string
  opportunity_id: number
  report_id: number
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | string
  suggested_next_action: string
}

export interface OperationDataGap {
  type: string
  message: string
  suggested_action: string
}

export interface OperationNextAction {
  action: string
  label: string
  enabled: boolean
  reason: string
}

export interface OperationRunResponse {
  id: number
  account_id: number
  data_refresh_run_id: number | null
  evidence_refresh_run_id: number | null
  report_id: number | null
  trigger_type: string
  status: OperationRunStatus
  analysis_date: string | null
  summary: string | null
  recommendations: OperationRecommendation[]
  data_gaps: OperationDataGap[]
  next_actions: OperationNextAction[]
  stats: Record<string, unknown>
  error_code: string | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}
