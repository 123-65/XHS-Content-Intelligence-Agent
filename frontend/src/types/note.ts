export type NoteSourceType = '自己账号' | '竞品' | '关键词' | '手动链接'
export type CollectStatus = 'SUCCESS' | 'PENDING' | 'FAILED'

export interface NoteSnapshot {
  id: string
  title: string
  author: string
  sourceType: NoteSourceType
  keyword: string
  content: string
  tags: string[]
  imageUrls: string[]
  imageCount: number
  hasOcr: boolean
  ocrText: string
  mergedText: string
  likes: number
  collects: number
  comments: number
  status: CollectStatus
  collectedAt: string
  originalUrl: string
}

export interface FailedCollectRecord {
  url: string
  reason: string
  retryable: boolean
}
