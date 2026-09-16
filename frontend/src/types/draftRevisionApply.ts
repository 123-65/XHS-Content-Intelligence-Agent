export type DraftRevisionApplyStatus =
  | 'WAITING_CONFIRMATION'
  | 'CREATED'
  | 'STALE_PLAN'
  | 'PROVIDER_NOT_CONFIGURED'
  | 'FAILED'
  | 'BLOCKED'

export interface DraftRevisionApplyRequest {
  account_id: number
  confirmed: boolean
  user_extra_requirements?: string | null
  save_as?: 'NEW_DRAFT'
  source_draft_id?: number | null
}

export interface AppliedRevisionOperation {
  operation_order: number
  target: string
  action: string
  result: string
}

export interface DraftRevisionApplyDraft {
  title: string
  content: string
  tags: string[]
  cta: string | null
}

export interface DraftRevisionApplyResponse {
  status: DraftRevisionApplyStatus
  account_id: number
  revision_plan_id: number
  source_draft_id: number | null
  revised_draft_id: number | null
  review_report_id: number | null
  summary: string
  applied_operations: AppliedRevisionOperation[]
  draft: DraftRevisionApplyDraft | null
  warnings: string[]
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
}
