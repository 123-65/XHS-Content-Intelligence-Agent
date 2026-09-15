export type OperationExperimentStatus = 'WAITING_CONFIRMATION' | 'CREATED' | 'DATA_INSUFFICIENT' | 'FAILED'

export interface OperationExperimentRequest {
  account_id: number
  confirmed?: boolean
  experiment_name?: string | null
  target_metric?: 'like' | 'collect' | 'comment' | 'lead' | 'order' | 'engagement'
  notes?: string | null
}

export interface OperationExperimentResponse {
  status: OperationExperimentStatus
  run_id: number
  rank: number
  account_id: number | null
  opportunity_id: number | null
  experiment_id: number | null
  preview: Record<string, unknown>
  confirmation: Record<string, unknown>
  error_code: string | null
  error_message: string | null
}
