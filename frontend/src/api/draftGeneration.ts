import { apiClient } from './client'
import type { DraftGenerationRequest, DraftGenerationResponse } from '@/types/draftGeneration'

export const generateDraft = (experimentId: number, data: DraftGenerationRequest) =>
  apiClient.post<unknown, DraftGenerationResponse>(
    `/agent/content-experiments/${experimentId}/drafts/generate`,
    data
  )
