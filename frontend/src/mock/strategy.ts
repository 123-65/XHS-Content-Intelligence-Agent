import type { StrategyMemory } from '@/types/experiment'

export const strategyMemories: StrategyMemory[] = [
  {
    id: 'mem-001',
    category: '有效选题模式',
    content: '项目拆解类内容要明确“适合写进简历”的交付物，并展示输入、处理、输出、指标四段结构。',
    weight: 86,
    enabled: true,
    sourceExperiment: 'FastAPI + OpenAI SDK 简历项目拆解',
    relatedMetric: '私信 31 / 成交 2',
    createdAt: '2026-09-03',
    updatedAt: '2026-09-05'
  },
  {
    id: 'mem-002',
    category: '标题结构',
    content: '“人群限定 + 错误路径 + 替代方案”适合承接学习路线和避坑内容。',
    weight: 92,
    enabled: true,
    sourceExperiment: '普通大学生 AI Agent 学习路线',
    relatedMetric: '收藏率 2.90%',
    createdAt: '2026-09-04',
    updatedAt: '2026-09-05'
  },
  {
    id: 'mem-003',
    category: '失败选题模式',
    content: '纯工具推荐类内容虽然曝光高，但私信转化弱，除非绑定具体项目任务。',
    weight: 58,
    enabled: true,
    sourceExperiment: 'AI 工具合集低转化验证',
    relatedMetric: '曝光 4.8w / 私信 4',
    createdAt: '2026-08-30',
    updatedAt: '2026-09-01'
  },
  {
    id: 'mem-004',
    category: 'CTA 模式',
    content: '资料包 CTA 使用“评论关键词 + 私信关键词”双入口，能减少用户行动成本。',
    weight: 74,
    enabled: true,
    sourceExperiment: 'FastAPI + OpenAI SDK 简历项目拆解',
    relatedMetric: '线索 18',
    createdAt: '2026-09-03',
    updatedAt: '2026-09-05'
  },
  {
    id: 'mem-005',
    category: '转化洞察',
    content: '用户最愿意为“项目陪跑”和“简历表达”付费，而不是为工具清单付费。',
    weight: 81,
    enabled: true,
    sourceExperiment: '内容实验复盘',
    relatedMetric: '成交金额 1398',
    createdAt: '2026-09-05',
    updatedAt: '2026-09-05'
  }
]
