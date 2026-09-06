import type { AccountProfile } from '@/types/account'

export const accountProfile: AccountProfile = {
  id: 'acc-ai-study',
  name: 'AI项目学习号',
  homepageUrl: 'https://www.xiaohongshu.com/user/profile/ai-project-learning',
  positioning: '面向普通大学生和转行学习者的 AI 项目实战账号',
  targetUser: '想把 AI 项目写进简历、但不知道从哪里开始的本科生和应届生',
  businessModel: '低价训练营引流 + 项目陪跑咨询 + 简历修改服务',
  coreProduct: 'FastAPI + OpenAI SDK AI Agent 项目陪跑营',
  leadValue: 39,
  averageOrderValue: 699,
  grossProfit: 430,
  primaryGoal: '私信',
  stylePreference: '项目拆解、路径清晰、少讲概念、多给可落地步骤',
  forbiddenTopics: '夸大就业承诺、贩卖焦虑、未经验证的自动化发帖教程',
  strategySummary: [
    '学习路线内容要把“先学业务闭环，再学框架”放在前 3 行',
    '标题里出现“普通大学生”“可写进简历”更容易触发收藏',
    'CTA 优先引导评论关键词和私信资料包，不直接强推课程'
  ]
}
