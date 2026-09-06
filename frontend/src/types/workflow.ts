export type RunStatus = 'SUCCESS' | 'RUNNING' | 'FAILED' | 'PENDING'

export interface WorkflowRun {
  id: string
  type: string
  experimentName: string
  status: RunStatus
  startedAt: string
  endedAt?: string
  duration: string
  errorMessage?: string
}

export interface NodeRun {
  id: string
  workflowRunId: string
  name: string
  status: RunStatus
  inputSummary: string
  outputSummary: string
  duration: string
  retries: number
  tokenUsage: number
  cost: number
  errorMessage?: string
  inputSnapshot: Record<string, unknown>
  outputSnapshot: Record<string, unknown>
  promptTokens: number
  completionTokens: number
  totalTokens: number
  estimatedCost: number
}
