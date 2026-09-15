import { apiClient } from './client'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface AccountProfileResponse {
  id: number
  account_name: string
  platform: string
  homepage_url: string | null
  content_domain: string | null
  positioning: string
  target_audience: string
  persona: string | null
  monetization_goal: string | null
  business_model: string | null
  main_product: string | null
  lead_value: string
  avg_order_value: string
  gross_profit: string
  primary_goal: string
  tone_preference: string | null
  forbidden_topics: string | null
  risk_preference: string
  account_stage: string
  created_at: string
  updated_at: string
}

export interface AccountProfileCreatePayload {
  account_name: string
  platform: string
  homepage_url?: string | null
  content_domain?: string | null
  positioning: string
  target_audience: string
  primary_goal?: string
}

const unwrap = <T>(response: ApiResponse<T>) => {
  if (response.code !== 0) {
    throw new Error(response.message || 'AccountProfile request failed')
  }
  return response.data
}

export const getAccountProfiles = async () =>
  unwrap(await apiClient.get<unknown, ApiResponse<AccountProfileResponse[]>>('/accounts'))

export const createAccountProfile = async (data: AccountProfileCreatePayload) =>
  unwrap(await apiClient.post<unknown, ApiResponse<AccountProfileResponse>>('/accounts', data))

export const getAccountProfileDetail = async (id: number) =>
  unwrap(await apiClient.get<unknown, ApiResponse<AccountProfileResponse>>(`/accounts/${id}`))

export const updateAccountProfile = async (id: number, data: Partial<AccountProfileCreatePayload>) =>
  unwrap(await apiClient.put<unknown, ApiResponse<AccountProfileResponse>>(`/accounts/${id}`, data))
