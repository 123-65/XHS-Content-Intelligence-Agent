import { apiClient } from './client'
import type { AccountProfile } from '@/types/account'

export const getAccounts = () => apiClient.get<AccountProfile[]>('/accounts')
export const createAccount = (data: Partial<AccountProfile>) => apiClient.post<AccountProfile>('/accounts', data)
export const getAccountDetail = (id: string) => apiClient.get<AccountProfile>(`/accounts/${id}`)
export const updateAccount = (id: string, data: Partial<AccountProfile>) =>
  apiClient.put<AccountProfile>(`/accounts/${id}`, data)
