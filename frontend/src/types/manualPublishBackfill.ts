export type ManualPublishBackfillStatus = 'WAITING_CONFIRMATION' | 'RECORDED' | 'FAILED'

export interface ManualPublishBackfillRequest {
  account_id: number
  confirmed: boolean
  platform?: 'xhs'
  note_url: string
  published_at?: string | null
  title?: string | null
  like_count?: number
  collect_count?: number
  comment_count?: number
  share_count?: number
  follower_gain?: number
  lead_count?: number
  remark?: string | null
  snapshot_window?: string
}

export interface ManualPublishMetrics {
  like_count: number
  collect_count: number
  comment_count: number
  share_count: number
  follower_gain: number
  lead_count: number
  source_type: string
}

export interface ManualPublishNextAction {
  action: string
  label: string
  enabled: boolean
}

export interface ManualPublishBackfillResponse {
  status: ManualPublishBackfillStatus
  account_id: number
  package_id: number | null
  published_note_id: number | null
  metric_snapshot_id: number | null
  private_conversion_snapshot_id: number | null
  note_url: string
  published_at: string | null
  metrics: ManualPublishMetrics | null
  warnings: string[]
  next_actions: ManualPublishNextAction[]
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
}

export interface PublishedNoteBackfillResponse {
  id: number
  account_id: number
  experiment_id: number
  draft_id: number
  package_id: number | null
  publish_url: string
  platform: string
  status: string
  source_type: string
  published_at: string | null
  raw_snapshot: Record<string, any>
  created_at: string
  updated_at: string
}
