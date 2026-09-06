import type { BusinessMetrics, PerformanceReport, PublicMetrics } from '@/types/metrics'

export const publicMetrics: PublicMetrics = {
  experimentId: 'exp-002',
  likes: 1240,
  collects: 830,
  comments: 76,
  views: 28600,
  collectedAt: '2026-09-05 22:20',
  trend: [
    { date: '09-01', likes: 210, collects: 130, comments: 13 },
    { date: '09-02', likes: 380, collects: 244, comments: 21 },
    { date: '09-03', likes: 620, collects: 418, comments: 38 },
    { date: '09-04', likes: 900, collects: 620, comments: 56 },
    { date: '09-05', likes: 1240, collects: 830, comments: 76 }
  ]
}

export const businessMetrics: BusinessMetrics = {
  experimentId: 'exp-002',
  privateMessages: 31,
  leads: 18,
  deals: 2,
  revenue: 1398,
  note: '私信关键词以“项目”和“路线”为主，2 人转化为陪跑营。'
}

export const performanceReport: PerformanceReport = {
  experimentId: 'exp-002',
  likeRate: '4.34%',
  collectRate: '2.90%',
  commentRate: '0.27%',
  leadRate: '58.06%',
  businessValue: 2097,
  roi: '6.2',
  goalReached: true,
  successReasons: ['标题直接命中“简历项目”场景', '正文给了可执行路线，收藏动机强', 'CTA 关键词清晰，私信承接顺畅'],
  failureReasons: ['评论区追问集中在部署问题，正文没有提前解释', '封面第 3 张信息密度略高'],
  nextActions: ['新增一篇“项目如何部署上线”的实验', '把“输入-处理-输出-指标”沉淀为标题结构策略', '后续工具清单类内容只作为系列补充'],
  updateStrategyMemory: true
}

export const dashboardTrend = [
  { title: 'LangGraph 避坑路线', likes: 3260, collects: 2180, comments: 184 },
  { title: 'FastAPI 项目拆解', likes: 1988, collects: 1542, comments: 96 },
  { title: 'AI 学习账号复盘', likes: 1420, collects: 996, comments: 73 },
  { title: 'OpenAI SDK 入门', likes: 1180, collects: 760, comments: 64 },
  { title: '项目写简历模板', likes: 1320, collects: 980, comments: 88 },
  { title: '工具合集', likes: 2450, collects: 680, comments: 44 },
  { title: '内容情报系统', likes: 860, collects: 520, comments: 49 }
]

export const businessValueByType = [
  { type: '项目拆解', value: 2097 },
  { type: '学习路线', value: 1755 },
  { type: '避坑经验', value: 1360 },
  { type: '工具推荐', value: 260 }
]
