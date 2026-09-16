import { apiClient } from './client'
import type { DraftReviewRequest, DraftReviewResponse } from '@/types/draftReview'

export const reviewDraft = (draftId: number, data: DraftReviewRequest) =>
  apiClient.post<unknown, DraftReviewResponse>(`/agent/drafts/${draftId}/review`, data)
