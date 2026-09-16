import { apiClient } from './client'
import type {
  StrategyMemoryConfirmationRequest,
  StrategyMemoryConfirmationResponse,
  StrategyMemoryItem
} from '@/types/strategyMemoryConfirmation'

export const getStrategyMemoryCandidates = (reviewId: number) =>
  apiClient.get<unknown, StrategyMemoryConfirmationResponse>(
    `/agent/post-publish-reviews/${reviewId}/strategy-memory-candidates`
  )

export const confirmStrategyMemories = (reviewId: number, data: StrategyMemoryConfirmationRequest) =>
  apiClient.post<unknown, StrategyMemoryConfirmationResponse>(
    `/agent/post-publish-reviews/${reviewId}/strategy-memories/confirm`,
    data
  )

export const listAccountStrategyMemories = (accountId: number) =>
  apiClient.get<unknown, StrategyMemoryItem[]>(`/agent/accounts/${accountId}/strategy-memories`)
