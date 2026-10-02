import { apiClient } from './client'
import type { AgentRunResponse, AgentTurnRequest, AgentTurnResponse, ConversationMessagePage } from '@/types/unifiedAgent'
import type { DraftDetail, DraftSummary, ListPage, PrivateMetricSnapshotResult, PrivateMetricsWriteRequest, PublicationDetail, PublicationSummary, PublishPackageResult, PublishedNoteResult, ResearchDetail, ResearchSummary, ReviewSummary, StrategyDetail, StrategySummary } from '@/types/productRead'

export const sendAgentTurn = (data: AgentTurnRequest) =>
  apiClient.post<unknown, AgentTurnResponse>('/api/agent/turns', data, { timeout: 180000 })

export const getAgentRun = (runRef: string, accountRef: number, signal?: AbortSignal) =>
  apiClient.get<unknown, AgentRunResponse>(`/api/agent/runs/${encodeURIComponent(runRef)}`, {
    params: { account_ref: accountRef }, signal
  })

// Backend currently supports a bounded latest window, but no cursor/before pagination.
export const getConversationMessages = (conversationId: number, accountRef: number, limit = 40, beforeId?: number | null, signal?: AbortSignal) =>
  apiClient.get<unknown, ConversationMessagePage>(`/agent/conversations/${conversationId}/messages`, {
    params: { account_ref: accountRef, limit, ...(beforeId ? { before_id: beforeId } : {}) }, signal
  })

const detail = <T>(path: string, accountRef: number, signal?: AbortSignal) =>
  apiClient.get<unknown, T>(path, { params: { account_ref: accountRef }, signal })

export const getResearchDetail = (ref: number, accountRef: number, signal?: AbortSignal) => detail<ResearchDetail>(`/api/artifacts/research/${ref}`, accountRef, signal)
export const getStrategyDetail = (ref: number, accountRef: number, signal?: AbortSignal) => detail<StrategyDetail>(`/api/artifacts/strategy/${ref}`, accountRef, signal)
export const getDraftDetail = (ref: number, accountRef: number, signal?: AbortSignal) => detail<DraftDetail>(`/api/artifacts/draft/${ref}`, accountRef, signal)
export const getPublicationDetail = (ref: number, accountRef: number, signal?: AbortSignal) => detail<PublicationDetail>(`/api/publications/${ref}`, accountRef, signal)

const list = <T>(path: string, accountRef: number, pageNo: number, pageSize: number, signal?: AbortSignal) =>
  apiClient.get<unknown, ListPage<T>>(path, {
    params: { account_ref: accountRef, page_no: pageNo, page_size: pageSize }, signal
  })

export const getResearchList = (accountRef: number, pageNo = 1, pageSize = 20, signal?: AbortSignal) => list<ResearchSummary>('/api/artifacts/research', accountRef, pageNo, pageSize, signal)
export const getStrategyList = (accountRef: number, pageNo = 1, pageSize = 20, signal?: AbortSignal) => list<StrategySummary>('/api/artifacts/strategy', accountRef, pageNo, pageSize, signal)
export const getDraftList = (accountRef: number, pageNo = 1, pageSize = 20, signal?: AbortSignal) => list<DraftSummary>('/api/artifacts/draft', accountRef, pageNo, pageSize, signal)
export const getPublicationList = (accountRef: number, pageNo = 1, pageSize = 20, signal?: AbortSignal) => list<PublicationSummary>('/api/publications', accountRef, pageNo, pageSize, signal)
export const getReviewList = (accountRef: number, pageNo = 1, pageSize = 20, signal?: AbortSignal) => list<ReviewSummary>('/api/reviews', accountRef, pageNo, pageSize, signal)
export const createPublishPackage = (data: { account_id: number; draft_version_id: number }) =>
  apiClient.post<unknown, PublishPackageResult>('/api/publish-packages', data)
export const registerPublishedNote = (data: { account_id: number; publish_package_ref: number; publish_url: string; published_at: string }) =>
  apiClient.post<unknown, PublishedNoteResult>('/api/published-notes', data)
export const recordPrivateMetrics = (publishedNoteRef: number, data: PrivateMetricsWriteRequest) =>
  apiClient.post<unknown, PrivateMetricSnapshotResult>(`/api/published-notes/${publishedNoteRef}/private-metrics`, data)
