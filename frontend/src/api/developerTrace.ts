import { apiClient } from './client'
import type { ApiResponse, DeveloperAgentRunDetail, DeveloperAgentRunSummary, DeveloperAgentStepTrace } from '@/types/developerTrace'

export const getDeveloperAgentRuns = (params?: { limit?: number }) =>
  apiClient.get<unknown, ApiResponse<DeveloperAgentRunSummary[]>>('/api/developer/agent-runs', { params })

export const getDeveloperAgentRun = (runId: number) =>
  apiClient.get<unknown, ApiResponse<DeveloperAgentRunDetail>>(`/api/developer/agent-runs/${runId}`)

export const getDeveloperAgentSteps = (runId: number) =>
  apiClient.get<unknown, ApiResponse<DeveloperAgentStepTrace[]>>(`/api/developer/agent-runs/${runId}/steps`)

export const getLatestDeveloperRun = () =>
  apiClient.get<unknown, ApiResponse<DeveloperAgentRunDetail>>('/api/developer/latest-run')

export const getLatestDeveloperSteps = () =>
  apiClient.get<unknown, ApiResponse<DeveloperAgentStepTrace[]>>('/api/developer/latest-run/steps')

