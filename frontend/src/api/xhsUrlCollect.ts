import { apiClient } from './client'
import type { XhsUrlCollectRequest, XhsUrlCollectResponse } from '@/types/xhsUrlCollect'

export const collectXhsUrls = (data: XhsUrlCollectRequest) =>
  apiClient.post<unknown, XhsUrlCollectResponse>('/agent/xhs/url-collect', data)

export const listXhsUrlCollectRuns = (params?: { account_id?: number; limit?: number }) =>
  apiClient.get<unknown, XhsUrlCollectResponse[]>('/agent/xhs/url-collect/runs', { params })

export const getXhsUrlCollectRun = (runId: number) =>
  apiClient.get<unknown, XhsUrlCollectResponse>(`/agent/xhs/url-collect/runs/${runId}`)
