import type { CompetitorAnalysisReport, Experiment } from '@/types/experiment'
import type { Draft, ReviewReport } from '@/types/draft'

export const competitorAnalysisReport: CompetitorAnalysisReport = {
  id: 'analysis-agent-roadmap',
  keyword: 'AI Agent 学习路线',
  objective: '私信转化参考',
  topics: ['不要一上来学 LangGraph', '普通大学生 AI 项目路线', 'FastAPI + OpenAI SDK 实战', '项目如何写进简历'],
  titleStructures: ['反常识提醒 + 人群限定', '时间承诺 + 项目结果', '错误路径 + 替代方案'],
  tags: ['AI Agent', 'AI项目', '大学生求职', 'FastAPI', 'OpenAI SDK'],
  contentStructures: ['先指出常见误区', '给出阶段路线', '展示可交付项目', '用评论/私信承接资料包'],
  ctas: ['评论“路线”领取项目清单', '私信“项目”拿 FastAPI 模板', '收藏后按 4 步做'],
  learnings: ['具体人群越清晰，收藏率越稳定', '路线图内容适合做系列化实验', '封面要直接呈现“别先学框架”的冲突点'],
  avoidances: ['不要堆工具名', '不要承诺几天找到工作', '不要把自动化爬虫作为卖点'],
  topSamples: [
    {
      id: 'sample-001',
      title: '普通大学生做 AI Agent 项目，先别急着学 LangGraph',
      likes: 3260,
      collects: 2180,
      comments: 184,
      reason: '反常识观点击中学习路径焦虑，收藏动机强',
      reusablePoint: '标题前半句限定人群，后半句给出明确避坑'
    },
    {
      id: 'sample-002',
      title: 'FastAPI + OpenAI SDK：7 天做出能讲清楚的 AI 项目',
      likes: 1988,
      collects: 1542,
      comments: 96,
      reason: '技术栈可落地，和简历场景绑定',
      reusablePoint: '用“能讲清楚”替代夸张承诺'
    }
  ]
}

export const experiments: Experiment[] = [
  {
    id: 'exp-001',
    name: '普通大学生 AI Agent 学习路线',
    topicDirection: '学习路线',
    hypothesis: '用“先别学 LangGraph”切入，比工具合集更能提升收藏和私信',
    targetMetric: '私信线索数',
    expectedResult: '发布 72 小时内获得 18 条私信线索',
    topicAngle: '错误路径纠偏 + FastAPI 项目路线',
    status: 'READY',
    published: false,
    businessValue: 0,
    createdAt: '2026-09-05 10:30'
  },
  {
    id: 'exp-002',
    name: 'FastAPI + OpenAI SDK 简历项目拆解',
    topicDirection: '项目拆解',
    hypothesis: '把项目拆成输入、处理、输出、指标四段，可以提升评论提问率',
    targetMetric: '评论数',
    expectedResult: '评论率高于 3%',
    topicAngle: '可复述的项目结构',
    status: 'PUBLISHED',
    published: true,
    businessValue: 1280,
    createdAt: '2026-09-01 15:20',
    publishedAt: '2026-09-02 20:00',
    publishUrl: 'https://www.xiaohongshu.com/explore/mock-published-002'
  },
  {
    id: 'exp-003',
    name: 'AI 工具合集低转化验证',
    topicDirection: '工具推荐',
    hypothesis: '纯工具推荐曝光不错，但对私信线索帮助有限',
    targetMetric: '曝光与私信比',
    expectedResult: '验证工具清单是否适合做引流入口',
    topicAngle: '10 个提升效率的 AI 工具',
    status: 'ANALYZED',
    published: true,
    businessValue: 260,
    createdAt: '2026-08-28 11:05',
    publishedAt: '2026-08-29 19:40',
    publishUrl: 'https://www.xiaohongshu.com/explore/mock-published-003'
  }
]

export const draft: Draft = {
  id: 'draft-exp-001',
  experimentId: 'exp-001',
  titleCandidates: ['普通大学生做 AI Agent，先别急着学 LangGraph', '想做 AI 项目写简历？先按这 4 步来', 'FastAPI + OpenAI SDK：更适合新手的 AI 项目路线'],
  body: '很多同学一开始就去学 LangGraph，结果卡在框架概念里。\n\n更适合普通大学生的路线是：\n1. 先选一个真实场景，比如内容情报、简历分析、资料整理。\n2. 用 FastAPI 搭一个最小接口，让输入和输出跑通。\n3. 接 OpenAI SDK，把业务规则写成明确的 prompt 和评估标准。\n4. 最后再补数据库、任务日志和复盘报表。\n\n你要做的不是“看起来很 AI”，而是能讲清楚：解决谁的问题、怎么处理数据、结果如何评估。',
  tags: ['AI Agent', 'AI项目', 'FastAPI', 'OpenAI SDK', '大学生求职'],
  coverCopy: 'AI Agent 学习路线：先别急着学框架',
  imageScript: ['第1张：封面，AI Agent 学习路线', '第2张：为什么不要一上来学框架', '第3张：推荐学习顺序', '第4张：适合写进简历的项目方向', '第5张：评论/私信领取项目清单'],
  cta: '评论“路线”领取 AI 项目拆解清单，想要 FastAPI 模板可以私信“项目”。',
  updatedAt: '2026-09-05 20:30'
}

export const reviewReport: ReviewReport = {
  passed: true,
  qualityScore: 88,
  conversionScore: 82,
  riskLevel: 'LOW',
  issues: ['标题候选较多，可以优先选择冲突更强的一版', '正文第 4 步可以补一个项目日志例子'],
  suggestions: ['封面突出“别先学 LangGraph”', 'CTA 同时保留评论关键词和私信关键词', '避免出现“保证就业”等表述']
}
