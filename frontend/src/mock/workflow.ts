import type { NodeRun, WorkflowRun } from '@/types/workflow'

export const workflowRuns: WorkflowRun[] = [
  {
    id: 'run-001',
    type: '内容实验闭环',
    experimentName: '普通大学生 AI Agent 学习路线',
    status: 'SUCCESS',
    startedAt: '2026-09-05 20:01:12',
    endedAt: '2026-09-05 20:04:46',
    duration: '3m34s'
  },
  {
    id: 'run-002',
    type: '竞品采集与分析',
    experimentName: 'FastAPI + OpenAI SDK 简历项目拆解',
    status: 'SUCCESS',
    startedAt: '2026-09-04 18:20:05',
    endedAt: '2026-09-04 18:23:11',
    duration: '3m06s'
  },
  {
    id: 'run-003',
    type: '指标回采',
    experimentName: 'AI 工具合集低转化验证',
    status: 'FAILED',
    startedAt: '2026-09-03 22:10:32',
    endedAt: '2026-09-03 22:11:10',
    duration: '38s',
    errorMessage: '公开链接不可访问，等待人工确认发布 URL'
  }
]

export const nodeRuns: NodeRun[] = [
  {
    id: 'node-001',
    workflowRunId: 'run-001',
    name: 'LoadAccountContext',
    status: 'SUCCESS',
    inputSummary: 'account_id=acc-ai-study',
    outputSummary: '加载账号定位、商业目标、策略摘要',
    duration: '180ms',
    retries: 0,
    tokenUsage: 0,
    cost: 0,
    inputSnapshot: { account_id: 'acc-ai-study' },
    outputSnapshot: { primary_goal: '私信', core_product: 'FastAPI + OpenAI SDK 项目陪跑营' },
    promptTokens: 0,
    completionTokens: 0,
    totalTokens: 0,
    estimatedCost: 0
  },
  {
    id: 'node-002',
    workflowRunId: 'run-001',
    name: 'AnalyzeCompetitorPatterns',
    status: 'SUCCESS',
    inputSummary: '4 篇竞品笔记 + 私信转化目标',
    outputSummary: '输出 7 条选题模式与 3 条不建议模仿点',
    duration: '41s',
    retries: 0,
    tokenUsage: 6120,
    cost: 0.42,
    inputSnapshot: { notes: 4, objective: '私信转化参考' },
    outputSnapshot: { topics: ['学习路线', '项目拆解'], avoidances: ['纯工具清单'] },
    promptTokens: 3980,
    completionTokens: 2140,
    totalTokens: 6120,
    estimatedCost: 0.42
  },
  {
    id: 'node-003',
    workflowRunId: 'run-001',
    name: 'GenerateDraft',
    status: 'SUCCESS',
    inputSummary: '实验假设 + 策略记忆 + 竞品洞察',
    outputSummary: '生成标题候选、正文、标签、图片脚本和 CTA',
    duration: '58s',
    retries: 1,
    tokenUsage: 8420,
    cost: 0.58,
    inputSnapshot: { experiment_id: 'exp-001', strategy_memory_count: 5 },
    outputSnapshot: { draft_id: 'draft-exp-001', titles: 3, image_cards: 5 },
    promptTokens: 5290,
    completionTokens: 3130,
    totalTokens: 8420,
    estimatedCost: 0.58
  },
  {
    id: 'node-004',
    workflowRunId: 'run-001',
    name: 'ReviewDraft',
    status: 'SUCCESS',
    inputSummary: '草稿正文 + 风险规则',
    outputSummary: '审核通过，质量 88，转化 82，低风险',
    duration: '33s',
    retries: 0,
    tokenUsage: 4620,
    cost: 0.31,
    inputSnapshot: { draft_id: 'draft-exp-001', checks: ['质量', '转化', '风险'] },
    outputSnapshot: { passed: true, quality: 88, conversion: 82 },
    promptTokens: 3010,
    completionTokens: 1610,
    totalTokens: 4620,
    estimatedCost: 0.31
  }
]
