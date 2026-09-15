export type EvidenceRefreshRunStatus = 'RUNNING' | 'SUCCESS' | 'PARTIAL' | 'DATA_INSUFFICIENT' | 'FAILED'

export interface EvidenceRefreshRunCreate {
  account_id: number
  data_refresh_run_id?: number | null
  keyword?: string | null
  target_metric: string
  limit: number
  name?: string | null
}

export interface EvidenceRefreshRunResponse {
  id: number
  account_id: number
  data_refresh_run_id: number | null
  report_id: number | null
  trigger_type: string
  status: EvidenceRefreshRunStatus
  keyword: string | null
  target_metric: string
  limit: number
  stats: Record<string, unknown>
  error_code: string | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
  report_summary: string | null
  note_count: number
  comment_count: number
  opportunity_count: number
  breakdown_count: number
  data_quality: string | null
  hint: string | null
}
