import { apiClient } from './client'
import type { DraftRevisionPlanRequest, DraftRevisionPlanResponse } from '@/types/draftRevision'

export const createDraftRevisionPlan = (draftId: number, data: DraftRevisionPlanRequest) =>
  apiClient.post<unknown, DraftRevisionPlanResponse>(`/agent/drafts/${draftId}/revision-plans`, data)
