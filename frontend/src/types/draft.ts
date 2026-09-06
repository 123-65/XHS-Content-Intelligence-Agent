export interface Draft {
  id: string
  experimentId: string
  titleCandidates: string[]
  body: string
  tags: string[]
  coverCopy: string
  imageScript: string[]
  cta: string
  updatedAt: string
}

export interface ReviewReport {
  passed: boolean
  qualityScore: number
  conversionScore: number
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH'
  issues: string[]
  suggestions: string[]
}
