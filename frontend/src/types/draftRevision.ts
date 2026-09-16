export type DraftRevisionPlanStatus =
  | 'WAITING_CONFIRMATION'
  | 'PENDING'
  | 'READY'
  | 'FAILED'
  | 'PROVIDER_NOT_CONFIGURED'
  | 'CANCELLED'
  | 'APPLIED'

export type RevisionPlanAction =
  | 'REWRITE'
  | 'SHORTEN'
  | 'EXPAND'
  | 'REMOVE'
  | 'SOFTEN'
  | 'STRENGTHEN'
  | 'ALIGN_EVIDENCE'
  | 'FIX_RISK'
  | 'PRESERVE'

export type RevisionPlanTarget =
  | 'TITLE'
  | 'INTRO'
  | 'BODY'
  | 'CTA'
  | 'TAGS'
  | 'TONE'
  | 'FACTUAL_CLAIM'
  | 'WHOLE_DRAFT'

export interface DraftRevisionPlanRequest {
  account_id: number
  confirmed: boolean
  review_report_id?: number | null
  conversation_id?: number | null
  feedback_text: string
  feedback_scope?: RevisionPlanTarget[]
}

export interface RevisionOperation {
  order: number
  target: RevisionPlanTarget
  action: RevisionPlanAction
  reason: string
  instruction: string
  priority: 'LOW' | 'MEDIUM' | 'HIGH'
}

export interface DraftRevisionPlanResponse {
  status: DraftRevisionPlanStatus
  account_id: number
  draft_id: number
  plan_id: number | null
  review_report_id: number | null
  conversation_id: number | null
  feedback_scope: string[]
  summary: string
  operations: RevisionOperation[]
  preserve: string[]
  must_not_change: string[]
  risk_fixes: string[]
  ready_for_revision: boolean
  base_draft_updated_at: string | null
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
}
