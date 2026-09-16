import { apiClient } from './client'
import type { PublishPackageRequest, PublishPackageResponse } from '@/types/publishPackage'

export const createPublishPackage = (draftId: number, data: PublishPackageRequest) =>
  apiClient.post<unknown, PublishPackageResponse>(`/agent/drafts/${draftId}/publish-packages`, data)

export const listPublishPackages = (draftId: number) =>
  apiClient.get<unknown, PublishPackageResponse[]>(`/agent/drafts/${draftId}/publish-packages`)

export const getPublishPackage = (packageId: number) =>
  apiClient.get<unknown, PublishPackageResponse>(`/agent/publish-packages/${packageId}`)
