import { apiClient } from './client'
import type { DataSourceConfigResponse, DataSourceConfigUpsert } from '@/types/dataSourceConfig'

export const getDataSourceConfigByAccount = (accountId: number, platform = 'xhs') =>
  apiClient.get<unknown, DataSourceConfigResponse>(`/agent/data-source-configs/by-account/${accountId}`, {
    params: { platform }
  })

export const upsertDataSourceConfig = (data: DataSourceConfigUpsert) =>
  apiClient.post<unknown, DataSourceConfigResponse>('/agent/data-source-configs', data)
