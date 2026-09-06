import { apiClient } from './client'
import type { Experiment } from '@/types/experiment'

export const getExperiments = (params?: Record<string, unknown>) => apiClient.get<Experiment[]>('/experiments', { params })
export const createExperiment = (data: Partial<Experiment>) => apiClient.post<Experiment>('/experiments', data)
export const getExperimentDetail = (id: string) => apiClient.get<Experiment>(`/experiments/${id}`)
export const updateExperiment = (id: string, data: Partial<Experiment>) => apiClient.put<Experiment>(`/experiments/${id}`, data)
export const getExperimentTimeline = (id: string) => apiClient.get(`/experiments/${id}/timeline`)
export const createExperimentFromAnalysis = (analysisId: string) =>
  apiClient.post<Experiment>(`/competitor-analysis/${analysisId}/create-experiment`)
