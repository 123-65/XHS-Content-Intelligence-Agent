export type DraftGenerationStatus =
  | 'WAITING_CONFIRMATION'
  | 'CREATED'
  | 'DATA_INSUFFICIENT'
  | 'PROVIDER_NOT_CONFIGURED'
  | 'BLOCKED'
  | 'FAILED'

export interface DraftGenerationRequest {
  account_id: number
  confirmed: boolean
  user_requirements?: string | null
  draft_type?: string
  tone?: string
  model_profile?: string
}

export interface DraftGenerationDraft {
  title: string
  content: string
  tags: string[]
  cta: string | null
}

export interface DraftGenerationResponse {
  status: DraftGenerationStatus
  account_id: number
  experiment_id: number
  draft_id: number | null
  ready_for_generation: boolean
  context_preview_status: string | null
  provider: string
  draft: DraftGenerationDraft | null
  warnings: string[]
  missing_context: Array<Record<string, any>>
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
}
