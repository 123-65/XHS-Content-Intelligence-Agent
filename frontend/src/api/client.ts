import axios from 'axios'

/**
 * 统一 API 客户端。
 * 开发环境默认使用相对路径，由 Vite proxy 转发到 backend 容器。
 * 如部署环境显式配置 VITE_API_BASE_URL，则使用该地址。
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000
})

apiClient.interceptors.response.use((response) => response.data)