import { apiClient } from './client'
import type { NoteSnapshot } from '@/types/note'

export const crawlNote = (data: { url: string }) => apiClient.post<NoteSnapshot>('/xhs/notes/crawl', data)
export const batchCrawlNotes = (data: { urls: string[] }) =>
  apiClient.post<NoteSnapshot[]>('/xhs/notes/batch-crawl', data)
export const searchNotes = (data: { keyword: string; limit?: number }) =>
  apiClient.post<NoteSnapshot[]>('/xhs/notes/search', data)
export const getNoteSnapshots = (params?: Record<string, unknown>) =>
  apiClient.get<NoteSnapshot[]>('/xhs/notes/snapshots', { params })
export const getNoteSnapshotDetail = (id: string) => apiClient.get<NoteSnapshot>(`/xhs/notes/snapshots/${id}`)
