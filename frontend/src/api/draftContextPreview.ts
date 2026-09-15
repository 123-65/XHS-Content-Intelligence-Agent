import { apiClient } from './client'
import type { DraftContextPreviewRequest, DraftContextPreviewResponse } from '@/types/draftContextPreview'

export const previewDraftContext = (experimentId: number, data: DraftContextPreviewRequest) =>
  apiClient.post<unknown, DraftContextPreviewResponse>(
    `/agent/content-experiments/${experimentId}/draft-context/preview`,
    data
  )
