import { apiClient } from './client'
import type {
  AgentChatRequest,
  AgentChatResponse,
  ConversationCurrentState,
  ConversationMessageResponse,
  ConversationResponse
} from '@/types/agentChat'

export const previewAgentChat = (data: AgentChatRequest) =>
  apiClient.post<unknown, AgentChatResponse>('/agent/chat/preview', data)

export const executeReadonlyAgentChat = (data: AgentChatRequest) =>
  apiClient.post<unknown, AgentChatResponse>('/agent/chat/execute-readonly', data)

export const createAgentConversation = (data: { account_id?: number | null; title?: string | null }) =>
  apiClient.post<unknown, ConversationResponse>('/agent/conversations', data)

export const getAgentConversation = (conversationId: number) =>
  apiClient.get<unknown, ConversationResponse>(`/agent/conversations/${conversationId}`)

export const listAgentConversationMessages = (conversationId: number, limit = 30) =>
  apiClient.get<unknown, ConversationMessageResponse[]>(`/agent/conversations/${conversationId}/messages`, {
    params: { limit }
  })

export const getAgentConversationState = (conversationId: number) =>
  apiClient.get<unknown, ConversationCurrentState>(`/agent/conversations/${conversationId}/state`)
