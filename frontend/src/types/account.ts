export interface AccountProfile {
  id: string
  name: string
  homepageUrl: string
  positioning: string
  targetUser: string
  businessModel: string
  coreProduct: string
  leadValue: number
  averageOrderValue: number
  grossProfit: number
  primaryGoal: '曝光' | '收藏' | '私信' | '成交'
  stylePreference: string
  forbiddenTopics: string
  strategySummary: string[]
}
