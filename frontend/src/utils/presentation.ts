export const statusLabel = (value: string | null | undefined) => ({
  WAITING_USER: '需要补充信息', PARTIAL_SUCCESS: '部分完成', FAILED: '执行失败',
  UNKNOWN: '暂无数据', USER_ATTRIBUTED: '用户填写', REVISED: '已修改',
  SUCCESS: '已完成', PUBLISHED: '已发布', GENERATED: '已生成', PROPOSED: '待确认',
  CONFIRMED: '已确认', REJECTED: '已拒绝', AVAILABLE: '已有数据', RUNNING: '执行中',
  PENDING: '等待处理', CANCELLED: '已取消'
}[value || ''] || value || '状态未知')

export const sourceLabel = (value: string | null | undefined) => ({
  USER_ATTRIBUTED: '用户填写', XHS_MCP: '小红书公开数据', MEASURED: '平台实测',
  AI_GENERATED: 'AI 生成', USER_REVISION: '用户修改', AI_REVISION: 'AI 修改', GENERATED: '初始生成'
}[value || ''] || value || '来源未知')

export const metricLabel = (value: string) => ({
  view_count: '浏览量', like_count: '点赞数', collect_count: '收藏数', comment_count: '评论数',
  share_count: '分享数', follow_count: '新增关注', profile_visit_count: '主页访问',
  dm_count: '私信咨询数', wechat_add_count: '微信新增数', consultation_count: '有效咨询数',
  deal_count: '成交数', revenue: '成交金额'
}[value] || value)

export const formatTime = (value: string | null | undefined) => value
  ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
  : '暂无时间'

export const displayMetric = (value: number | string | null | undefined) => value === null || value === undefined ? '未填写' : String(value)
