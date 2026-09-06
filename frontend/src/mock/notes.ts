import type { FailedCollectRecord, NoteSnapshot } from '@/types/note'

export const noteSnapshots: NoteSnapshot[] = [
  {
    id: 'note-001',
    title: '普通大学生做 AI Agent 项目，先别急着学 LangGraph',
    author: '阿青AI项目',
    sourceType: '竞品',
    keyword: 'AI Agent 学习路线',
    content: '很多同学第一步就冲框架，最后只会跑 demo。更稳的路线是：先用 FastAPI 做一个能解决真实问题的小系统，再逐步加记忆、工具调用和评估。',
    tags: ['AI Agent', '项目实战', '大学生求职'],
    imageUrls: ['https://images.unsplash.com/photo-1516321318423-f06f85e504b3'],
    imageCount: 5,
    hasOcr: true,
    ocrText: '先做业务闭环，再补框架能力',
    mergedText: '普通大学生做 AI Agent 项目 先别急着学 LangGraph FastAPI OpenAI SDK 项目闭环',
    likes: 3260,
    collects: 2180,
    comments: 184,
    status: 'SUCCESS',
    collectedAt: '2026-09-03 21:10',
    originalUrl: 'https://www.xiaohongshu.com/explore/mock-note-001'
  },
  {
    id: 'note-002',
    title: 'FastAPI + OpenAI SDK：7 天做出能讲清楚的 AI 项目',
    author: '简历项目研究所',
    sourceType: '关键词',
    keyword: 'FastAPI + OpenAI SDK 项目',
    content: '项目不是堆技术词，而是讲清输入、处理、输出、指标。这个模板适合做内容分析、知识库问答、运营助手。',
    tags: ['FastAPI', 'OpenAI SDK', '简历项目'],
    imageUrls: ['https://images.unsplash.com/photo-1515879218367-8466d910aaa4'],
    imageCount: 6,
    hasOcr: true,
    ocrText: '项目闭环 = 数据输入 + AI 处理 + 结果评估',
    mergedText: 'FastAPI OpenAI SDK 7 天 AI 项目 简历 项目闭环',
    likes: 1988,
    collects: 1542,
    comments: 96,
    status: 'SUCCESS',
    collectedAt: '2026-09-04 09:42',
    originalUrl: 'https://www.xiaohongshu.com/explore/mock-note-002'
  },
  {
    id: 'note-003',
    title: '小红书 AI 学习账号，为什么学习路线比工具合集更能转化',
    author: '小林做增长',
    sourceType: '竞品',
    keyword: '小红书 AI 学习账号',
    content: '工具合集容易有曝光，但用户看完就走。学习路线能承接“我该怎么开始”的焦虑，更适合引导私信领取资料。',
    tags: ['小红书运营', 'AI学习', '内容增长'],
    imageUrls: ['https://images.unsplash.com/photo-1553877522-43269d4ea984'],
    imageCount: 4,
    hasOcr: true,
    ocrText: '路线感比工具清单更有转化',
    mergedText: '小红书 AI 学习账号 学习路线 工具合集 私信转化',
    likes: 1420,
    collects: 996,
    comments: 73,
    status: 'SUCCESS',
    collectedAt: '2026-09-04 16:25',
    originalUrl: 'https://www.xiaohongshu.com/explore/mock-note-003'
  },
  {
    id: 'note-004',
    title: '我用内容情报系统复盘了 12 篇 AI 项目笔记',
    author: 'AI项目学习号',
    sourceType: '自己账号',
    keyword: '内容复盘',
    content: '收藏率高的内容都有一个共同点：先指出错误路径，再给替代方案。下一轮我会把封面改成问题 + 路线图。',
    tags: ['内容复盘', 'AI项目', '小红书运营'],
    imageUrls: ['https://images.unsplash.com/photo-1551288049-bebda4e38f71'],
    imageCount: 5,
    hasOcr: true,
    ocrText: '错误路径 + 替代路线 = 高收藏',
    mergedText: '内容情报系统 复盘 AI 项目笔记 收藏率 封面',
    likes: 860,
    collects: 520,
    comments: 49,
    status: 'SUCCESS',
    collectedAt: '2026-09-05 13:36',
    originalUrl: 'https://www.xiaohongshu.com/explore/mock-note-004'
  }
]

export const failedCollectRecords: FailedCollectRecord[] = [
  {
    url: 'https://www.xiaohongshu.com/explore/deleted-note',
    reason: '笔记已删除或不可公开访问',
    retryable: false
  },
  {
    url: 'https://www.xiaohongshu.com/user/profile/private-demo',
    reason: '主页短时间访问频率过高，建议稍后重试',
    retryable: true
  }
]
