import { apiClient } from './client'
import type { OperationExperimentRequest, OperationExperimentResponse } from '@/types/operationExperiment'

export const previewOperationExperiment = (runId: number, rank: number, data: OperationExperimentRequest) =>
  apiClient.post<unknown, OperationExperimentResponse>(
    `/agent/operation-runs/${runId}/recommendations/${rank}/experiment-preview`,
    data
  )

export const createOperationExperiment = (runId: number, rank: number, data: OperationExperimentRequest) =>
  apiClient.post<unknown, OperationExperimentResponse>(
    `/agent/operation-runs/${runId}/recommendations/${rank}/experiments`,
    data
  )
