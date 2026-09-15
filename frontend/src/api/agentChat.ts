import { apiClient } from './client'
import type { AgentChatRequest, AgentChatResponse } from '@/types/agentChat'

export const previewAgentChat = (data: AgentChatRequest) =>
  apiClient.post<unknown, AgentChatResponse>('/agent/chat/preview', data)

export const executeReadonlyAgentChat = (data: AgentChatRequest) =>
  apiClient.post<unknown, AgentChatResponse>('/agent/chat/execute-readonly', data)
