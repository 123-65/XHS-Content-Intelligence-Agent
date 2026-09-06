import { apiClient } from './client'
import type { StrategyMemory } from '@/types/experiment'

export const getStrategyMemories = (params?: Record<string, unknown>) =>
  apiClient.get<StrategyMemory[]>('/strategy-memories', { params })
export const createStrategyMemory = (data: Partial<StrategyMemory>) => apiClient.post<StrategyMemory>('/strategy-memories', data)
export const updateStrategyMemory = (id: string, data: Partial<StrategyMemory>) =>
  apiClient.put<StrategyMemory>(`/strategy-memories/${id}`, data)
export const deleteStrategyMemory = (id: string) => apiClient.delete(`/strategy-memories/${id}`)
