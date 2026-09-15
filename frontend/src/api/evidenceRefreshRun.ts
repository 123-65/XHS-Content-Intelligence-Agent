import { apiClient } from './client'
import type { EvidenceRefreshRunCreate, EvidenceRefreshRunResponse } from '@/types/evidenceRefreshRun'

export const createEvidenceRefreshRun = (data: EvidenceRefreshRunCreate) =>
  apiClient.post<unknown, EvidenceRefreshRunResponse>('/agent/evidence-refresh/runs', data)

export const listEvidenceRefreshRuns = (accountId: number, limit = 10) =>
  apiClient.get<unknown, EvidenceRefreshRunResponse[]>('/agent/evidence-refresh/runs', {
    params: { account_id: accountId, limit }
  })

export const getEvidenceRefreshRun = (runId: number) =>
  apiClient.get<unknown, EvidenceRefreshRunResponse>(`/agent/evidence-refresh/runs/${runId}`)
