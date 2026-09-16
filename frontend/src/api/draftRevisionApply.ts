import { apiClient } from './client'
import type { DraftRevisionApplyRequest, DraftRevisionApplyResponse } from '@/types/draftRevisionApply'

export const applyDraftRevisionPlan = (planId: number, data: DraftRevisionApplyRequest) =>
  apiClient.post<unknown, DraftRevisionApplyResponse>(`/agent/revision-plans/${planId}/apply`, data)
