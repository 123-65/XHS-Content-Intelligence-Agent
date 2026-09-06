export interface PublicMetrics {
  experimentId: string
  likes: number
  collects: number
  comments: number
  views: number
  collectedAt: string
  trend: Array<{ date: string; likes: number; collects: number; comments: number }>
}

export interface BusinessMetrics {
  experimentId: string
  privateMessages: number
  leads: number
  deals: number
  revenue: number
  note: string
}

export interface PerformanceReport {
  experimentId: string
  likeRate: string
  collectRate: string
  commentRate: string
  leadRate: string
  businessValue: number
  roi: string
  goalReached: boolean
  successReasons: string[]
  failureReasons: string[]
  nextActions: string[]
  updateStrategyMemory: boolean
}
