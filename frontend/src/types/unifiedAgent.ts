export type AgentAction =
  | 'RESPOND' | 'CLARIFY' | 'CONFIRM' | 'QUERY'
  | 'EXECUTE_PLAN' | 'EXECUTE_CONFIRMED_COMMAND' | 'CANCEL'

export type AgentStatus =
  | 'PENDING' | 'RUNNING' | 'WAITING_USER' | 'SUCCESS'
  | 'PARTIAL_SUCCESS' | 'FAILED' | 'CANCELLED'

export type ArtifactType =
  | 'RESEARCH' | 'CONTENT_STRATEGY' | 'CONTENT_OPPORTUNITY'
  | 'DRAFT' | 'DRAFT_REVIEW' | 'POST_PUBLISH_REVIEW' | 'STRATEGY_CANDIDATE'

export interface ArtifactRef { type: ArtifactType; id: number }

export interface PendingInteraction {
  type: 'CLARIFICATION' | 'CONFIRMATION'
  reason: string
  required_fields: string[]
  options: string[]
  related_run_ref: string | null
  resume_token: string
}

export interface WorkspaceSelection {
  research_ref?: number
  strategy_ref?: number
  opportunity_ref?: number
  draft_ref?: number
  published_note_ref?: number
}

export interface WorkspaceContextDisplay {
  type: string
  title: string
  version?: string
  detail_route: string
}

export interface AgentTurnRequest {
  conversation_id: number | null
  account_ref: number
  text: string
  workspace_selection?: WorkspaceSelection
  materials: { note_urls: string[]; profile_urls: string[] }
  client_request_id: string
}

export interface AgentTurnResult {
  action: AgentAction
  intent: string
  run_ref: string | null
  checkpoint_version: number | null
  message: string
  artifacts: ArtifactRef[]
  pending_interaction: PendingInteraction | null
  result: unknown
  warnings: string[]
  error: unknown
  status: AgentStatus
}

export interface AgentTurnResponse {
  conversation_id: number
  turn_id: number
  turn: AgentTurnResult
}

export interface AgentRunResponse {
  run_ref: string
  workflow_name: string
  account_ref: number
  status: AgentStatus
  checkpoint_version: number
  pending_interaction: PendingInteraction | null
  result: unknown
  warnings: string[]
  error: unknown
}

export interface ChatMessage {
  id: string
  role: 'USER' | 'ASSISTANT' | 'SYSTEM_STATUS'
  content: string
  createdAt: string
  status?: AgentStatus
  artifacts?: ArtifactRef[]
  warnings?: string[]
}

export interface ConversationMessage {
  id: number
  conversation_id: number
  role: 'USER' | 'ASSISTANT' | 'SYSTEM' | 'TOOL' | 'user' | 'assistant' | 'system'
  content: string
  message_type: string
  created_at: string
}

export interface ConversationMessagePage {
  items: ConversationMessage[]
  next_cursor: number | null
  has_more: boolean
}
