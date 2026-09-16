import { apiClient } from './client'
import type { PostPublishReviewRequest, PostPublishReviewResponse } from '@/types/postPublishReview'

export const createPostPublishReview = (publishedNoteId: number, data: PostPublishReviewRequest) =>
  apiClient.post<unknown, PostPublishReviewResponse>(
    `/agent/published-notes/${publishedNoteId}/post-publish-reviews`,
    data
  )

export const listPostPublishReviews = (publishedNoteId: number) =>
  apiClient.get<unknown, PostPublishReviewResponse[]>(`/agent/published-notes/${publishedNoteId}/post-publish-reviews`)

export const getPostPublishReview = (reviewId: number) =>
  apiClient.get<unknown, PostPublishReviewResponse>(`/agent/post-publish-reviews/${reviewId}`)
