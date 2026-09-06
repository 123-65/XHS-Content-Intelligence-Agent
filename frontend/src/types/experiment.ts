export type ExperimentStatus = 'DRAFT' | 'READY' | 'PUBLISHED' | 'METRICS_COLLECTED' | 'ANALYZED' | 'FAILED'

export interface CompetitorAnalysisReport {
  id: string
  keyword: string
  objective: string
  topics: string[]
  titleStructures: string[]
  tags: string[]
  contentStructures: string[]
  ctas: string[]
  learnings: string[]
  avoidances: string[]
  topSamples: Array<{
    id: string
    title: string
    likes: number
    collects: number
    comments: number
    reason: string
    reusablePoint: string
  }>
}

export interface Experiment {
  id: string
  name: string
  topicDirection: string
  hypothesis: string
  targetMetric: string
  expectedResult: string
  topicAngle: string
  status: ExperimentStatus
  published: boolean
  businessValue: number
  createdAt: string
  publishedAt?: string
  publishUrl?: string
}

export interface StrategyMemory {
  id: string
  category: string
  content: string
  weight: number
  enabled: boolean
  sourceExperiment: string
  relatedMetric: string
  createdAt: string
  updatedAt: string
}
