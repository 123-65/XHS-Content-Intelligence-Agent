import { apiClient } from './client'
import type { BusinessMetrics, PerformanceReport, PublicMetrics } from '@/types/metrics'

export const collectPublicMetrics = (data: { experimentId: string }) => apiClient.post<PublicMetrics>('/metrics/collect', data)
export const saveBusinessMetrics = (data: Partial<BusinessMetrics>) => apiClient.post<BusinessMetrics>('/business-metrics', data)
export const generatePerformanceReport = (experimentId: string) =>
  apiClient.post<PerformanceReport>(`/performance-reports/generate`, { experimentId })
export const getPerformanceReport = (experimentId: string) =>
  apiClient.get<PerformanceReport>(`/performance-reports/${experimentId}`)
