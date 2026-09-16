export type PublishPackageStatus =
  | 'WAITING_CONFIRMATION'
  | 'READY'
  | 'NEEDS_REVIEW'
  | 'DATA_INSUFFICIENT'
  | 'FAILED'

export interface PublishPackageRequest {
  account_id: number
  confirmed: boolean
  review_report_id?: number | null
  style?: string
  card_count?: number
}

export interface PublishCard {
  order: number
  card_type: string
  title: string
  subtitle?: string | null
  items: string[]
  style?: string | null
}

export interface PublishChecklistItem {
  item: string
  passed: boolean
  level: 'REQUIRED' | 'RECOMMENDED'
}

export interface PublishPackageResponse {
  status: PublishPackageStatus
  package_id: number | null
  account_id: number
  draft_id: number
  review_report_id: number | null
  revision_plan_id: number | null
  source_type: string
  title: string
  body: string
  tags: string[]
  cta: string | null
  cover_card: PublishCard | null
  image_cards: PublishCard[]
  publish_checklist: PublishChecklistItem[]
  warnings: string[]
  manual_publish_steps: string[]
  stats: Record<string, any>
  confirmation: Record<string, any>
  error_code: string | null
  error_message: string | null
  created_at?: string | null
  updated_at?: string | null
}
