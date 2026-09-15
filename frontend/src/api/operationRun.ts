import { apiClient } from './client'
import type { OperationRunCreate, OperationRunResponse } from '@/types/operationRun'

export const createOperationRun = (data: OperationRunCreate) =>
  apiClient.post<unknown, OperationRunResponse>('/agent/operation-runs', data)

export const listOperationRuns = (accountId: number, limit = 10) =>
  apiClient.get<unknown, OperationRunResponse[]>('/agent/operation-runs', {
    params: { account_id: accountId, limit }
  })

export const getOperationRun = (runId: number) =>
  apiClient.get<unknown, OperationRunResponse>(`/agent/operation-runs/${runId}`)
