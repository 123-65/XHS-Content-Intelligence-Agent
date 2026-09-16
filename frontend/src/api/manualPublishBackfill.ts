import { apiClient } from './client'
import type {
  ManualPublishBackfillRequest,
  ManualPublishBackfillResponse,
  PublishedNoteBackfillResponse
} from '@/types/manualPublishBackfill'

export const recordManualPublish = (packageId: number, data: ManualPublishBackfillRequest) =>
  apiClient.post<unknown, ManualPublishBackfillResponse>(`/agent/publish-packages/${packageId}/manual-publish`, data)

export const listBackfilledPublishedNotes = (params?: { account_id?: number; limit?: number }) =>
  apiClient.get<unknown, PublishedNoteBackfillResponse[]>('/agent/published-notes', { params })

export const getBackfilledPublishedNote = (publishedNoteId: number) =>
  apiClient.get<unknown, PublishedNoteBackfillResponse>(`/agent/published-notes/${publishedNoteId}`)
