export interface DataSourceKeyword {
  keyword: string
  enabled: boolean
  note?: string | null
}

export interface DataSourceCompetitorAccount {
  name?: string | null
  profile_url?: string | null
  platform_account_id?: string | null
  enabled: boolean
  note?: string | null
}

export interface DataSourceConfigUpsert {
  account_id: number
  platform: string
  status: 'ACTIVE' | 'DISABLED'
  keywords: DataSourceKeyword[]
  competitor_accounts: DataSourceCompetitorAccount[]
  note_urls: string[]
  refresh_policy: Record<string, unknown>
  metadata_payload: Record<string, unknown>
}

export interface DataSourceConfigResponse extends DataSourceConfigUpsert {
  id: number
  created_at: string
  updated_at: string
}
