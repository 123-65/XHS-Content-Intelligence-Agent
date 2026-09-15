export type RefreshTriggerType = 'USER_CLICK' | 'AGENT_COMMAND'

export type RefreshRunStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'PARTIAL' | 'FAILED' | 'PROVIDER_NOT_CONFIGURED'

export interface DataRefreshRunCreate {
  account_id: number
  data_source_config_id?: number | null
  trigger_type: RefreshTriggerType
  force?: boolean
}

export interface DataRefreshRunResponse {
  id: number
  account_id: number
  data_source_config_id: number | null
  trigger_type: string
  status: RefreshRunStatus
  refresh_scope_days: number
  started_at: string | null
  finished_at: string | null
  stats: Record<string, unknown>
  error_code: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}
