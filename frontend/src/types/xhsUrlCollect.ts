export type XhsUrlCollectRunStatus = 'WAITING_CONFIRMATION' | 'COMPLETED' | 'PARTIAL_SUCCESS' | 'FAILED'

export type XhsUrlCollectItemStatus =
  | 'SUCCESS'
  | 'PARTIAL_SUCCESS'
  | 'COLLECT_FAILED'
  | 'LOGIN_REQUIRED'
  | 'CAPTCHA_REQUIRED'
  | 'RATE_LIMITED'
  | 'UNSUPPORTED_URL'
  | 'PARSE_FAILED'

export interface XhsUrlCollectRequest {
  account_id: number
  confirmed: boolean
  urls: string[]
  collect_comments: boolean
  max_comments: number
}

export interface XhsUrlCollectAction {
  action: string
  label: string
  enabled: boolean
}

export interface XhsUrlCollectItemResult {
  url: string
  status: XhsUrlCollectItemStatus
  note_id: number | null
  xhs_note_snapshot_id: number | null
  competitor_account_id: number | null
  competitor_note_id: number | null
  comment_count_saved: number
  author_name: string | null
  title: string | null
  like_count: number | null
  collect_count: number | null
  comment_count: number | null
  warnings: string[]
  error_code: string | null
  error_message: string | null
}

export interface XhsUrlCollectResponse {
  status: XhsUrlCollectRunStatus
  account_id: number
  run_id: number | null
  total: number
  success_count: number
  failed_count: number
  results: XhsUrlCollectItemResult[]
  next_actions: XhsUrlCollectAction[]
  error_code: string | null
  error_message: string | null
  created_at: string | null
  finished_at: string | null
}
