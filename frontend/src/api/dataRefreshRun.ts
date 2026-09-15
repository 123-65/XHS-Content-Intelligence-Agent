import { apiClient } from './client'
import type { DataRefreshRunCreate, DataRefreshRunResponse } from '@/types/dataRefreshRun'

export const createDataRefreshRun = (data: DataRefreshRunCreate) =>
  apiClient.post<unknown, DataRefreshRunResponse>('/agent/data-refresh/runs', data)

export const listDataRefreshRuns = (accountId: number, limit = 10) =>
  apiClient.get<unknown, DataRefreshRunResponse[]>('/agent/data-refresh/runs', {
    params: { account_id: accountId, limit }
  })

export const getDataRefreshRun = (runId: number) =>
  apiClient.get<unknown, DataRefreshRunResponse>(`/agent/data-refresh/runs/${runId}`)
