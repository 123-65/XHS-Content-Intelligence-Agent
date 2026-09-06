import { apiClient } from './client'
import type { NodeRun, WorkflowRun } from '@/types/workflow'

export const getWorkflowRuns = (params?: Record<string, unknown>) => apiClient.get<WorkflowRun[]>('/workflow-runs', { params })
export const getWorkflowRunDetail = (id: string) => apiClient.get<WorkflowRun>(`/workflow-runs/${id}`)
export const getNodeRuns = (runId: string) => apiClient.get<NodeRun[]>(`/workflow-runs/${runId}/nodes`)
