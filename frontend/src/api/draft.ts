import { apiClient } from './client'
import type { Draft, ReviewReport } from '@/types/draft'

export const generateDraft = (data: Record<string, unknown>) => apiClient.post<Draft>('/drafts/generate', data)
export const reviewDraft = (draftId: string) => apiClient.post<ReviewReport>(`/drafts/${draftId}/review`)
export const getDraftDetail = (draftId: string) => apiClient.get<Draft>(`/drafts/${draftId}`)
export const updateDraft = (draftId: string, data: Partial<Draft>) => apiClient.put<Draft>(`/drafts/${draftId}`, data)
