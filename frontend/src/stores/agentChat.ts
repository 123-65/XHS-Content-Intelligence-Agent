import { defineStore } from 'pinia'
import { getConversationMessages, sendAgentTurn } from '@/api/unifiedAgent'
import type {
  AgentTurnRequest, ArtifactRef, ChatMessage, PendingInteraction, WorkspaceContextDisplay, WorkspaceSelection
} from '@/types/unifiedAgent'
import {
  isMissingOrForbiddenAccountContext, persistAccountRef, readPersistedAccountRef
} from './accountSelectionPersistence.mjs'

interface RetryState { request: AgentTurnRequest; userMessageId: string }

const now = () => new Date().toISOString()
const uid = () => crypto.randomUUID()

export const useAgentChatStore = defineStore('agent-chat', {
  state: () => ({
    conversation_id: null as number | null,
    account_ref: readPersistedAccountRef(),
    messages: [] as ChatMessage[],
    pending_interaction: null as PendingInteraction | null,
    active_run_ref: null as string | null,
    active_status: null as string | null,
    workspace_selection: {} as WorkspaceSelection,
    workspace_context_display: null as WorkspaceContextDisplay | null,
    is_sending: false,
    retry_state: null as RetryState | null,
    history_loading: false,
    history_loaded_for: null as number | null,
    history_next_cursor: null as number | null,
    history_has_more: false
  }),
  actions: {
    switchAccount(accountRef: number | null) {
      persistAccountRef(accountRef)
      if (this.account_ref === accountRef) return
      this.account_ref = accountRef
      this.conversation_id = null
      this.messages = []
      this.pending_interaction = null
      this.active_run_ref = null
      this.active_status = null
      this.workspace_selection = {}
      this.workspace_context_display = null
      this.retry_state = null
      this.history_loaded_for = null
      this.history_next_cursor = null
      this.history_has_more = false
    },
    clearRejectedAccount(error: unknown) {
      if (!isMissingOrForbiddenAccountContext(error)) return false
      this.switchAccount(null)
      return true
    },
    setWorkspaceSelection(selection: WorkspaceSelection, display?: WorkspaceContextDisplay) {
      this.workspace_selection = { ...selection }
      this.workspace_context_display = Object.keys(selection).length ? display || null : null
    },
    async loadRecentConversation(conversationId: number) {
      if (!this.account_ref) throw new Error('请先选择账号')
      if (this.history_loaded_for === conversationId) return
      this.history_loading = true
      try {
        const page = await getConversationMessages(conversationId, this.account_ref, 40)
        this.messages = page.items.map((item) => ({
          id: `server-${item.id}`,
          role: item.role.toUpperCase() === 'USER' ? 'USER' : item.role.toUpperCase() === 'ASSISTANT' ? 'ASSISTANT' : 'SYSTEM_STATUS',
          content: item.content,
          createdAt: item.created_at
        }))
        this.conversation_id = conversationId
        this.history_loaded_for = conversationId
        this.history_next_cursor = page.next_cursor
        this.history_has_more = page.has_more
      } finally {
        this.history_loading = false
      }
    },
    async loadEarlierMessages() {
      if (!this.conversation_id || !this.history_has_more || !this.history_next_cursor || this.history_loading) return
      this.history_loading = true
      try {
        if (!this.account_ref) throw new Error('请先选择账号')
        const page = await getConversationMessages(this.conversation_id, this.account_ref, 40, this.history_next_cursor)
        const older: ChatMessage[] = page.items.map((item) => ({
          id: `server-${item.id}`,
          role: item.role.toUpperCase() === 'USER' ? 'USER' : item.role.toUpperCase() === 'ASSISTANT' ? 'ASSISTANT' : 'SYSTEM_STATUS',
          content: item.content,
          createdAt: item.created_at
        }))
        const known = new Set(this.messages.map(item => item.id))
        this.messages = [...older.filter(item => !known.has(item.id)), ...this.messages]
        this.history_next_cursor = page.next_cursor
        this.history_has_more = page.has_more
      } finally {
        this.history_loading = false
      }
    },
    async sendNewTurn(text: string, materials: { note_urls: string[]; profile_urls: string[] }) {
      if (!this.account_ref) throw new Error('请先选择账号')
      const request: AgentTurnRequest = {
        conversation_id: this.conversation_id,
        account_ref: this.account_ref,
        text,
        workspace_selection: Object.keys(this.workspace_selection).length ? { ...this.workspace_selection } : undefined,
        materials,
        client_request_id: uid()
      }
      const userMessageId = uid()
      this.messages.push({ id: userMessageId, role: 'USER', content: text, createdAt: now() })
      this.retry_state = { request, userMessageId }
      return this.dispatch(this.retry_state)
    },
    async retryLastTurn() {
      if (!this.retry_state) throw new Error('没有可重试的请求')
      return this.dispatch(this.retry_state)
    },
    async dispatch(retry: RetryState) {
      this.is_sending = true
      try {
        const response = await sendAgentTurn(retry.request)
        const turn = response.turn
        this.conversation_id = response.conversation_id
        this.active_run_ref = turn.run_ref
        this.active_status = turn.status
        this.pending_interaction = turn.pending_interaction
        this.messages.push({
          id: `turn-${response.turn_id}`,
          role: 'ASSISTANT', content: turn.message, createdAt: now(), status: turn.status,
          artifacts: turn.artifacts, warnings: turn.warnings
        })
        this.retry_state = null
        return response
      } finally {
        this.is_sending = false
      }
    },
    artifactRoute(artifact: ArtifactRef) {
      if (artifact.type === 'RESEARCH') return `/agent/research/${artifact.id}`
      if (artifact.type === 'CONTENT_STRATEGY') return `/agent/strategy/${artifact.id}?type=strategy`
      if (artifact.type === 'CONTENT_OPPORTUNITY') return `/agent/strategy/${artifact.id}?type=opportunity`
      if (artifact.type === 'DRAFT' || artifact.type === 'DRAFT_REVIEW') return `/agent/draft/${artifact.id}`
      if (artifact.type === 'POST_PUBLISH_REVIEW' || artifact.type === 'STRATEGY_CANDIDATE') return `/agent/publication/${artifact.id}`
      return null
    }
  }
})
