import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/account', name: 'account', component: () => import('@/views/AccountProfile.vue') },
  { path: '/competitor/collect', name: 'competitorCollect', component: () => import('@/views/CompetitorCollect.vue') },
  { path: '/notes', name: 'notes', component: () => import('@/views/NoteLibrary.vue') },
  { path: '/competitor/analysis', name: 'competitorAnalysis', component: () => import('@/views/CompetitorAnalysis.vue') },
  { path: '/experiments', name: 'experiments', component: () => import('@/views/ExperimentList.vue') },
  { path: '/experiments/:id', name: 'experimentDetail', component: () => import('@/views/ExperimentDetail.vue') },
  { path: '/drafts', name: 'drafts', component: () => import('@/views/DraftWorkspace.vue') },
  { path: '/publish', name: 'publish', component: () => import('@/views/PublishAssistant.vue') },
  { path: '/metrics', name: 'metrics', component: () => import('@/views/MetricsReview.vue') },
  { path: '/strategy', name: 'strategy', component: () => import('@/views/StrategyMemory.vue') },
  { path: '/workflow-logs', name: 'workflowLogs', component: () => import('@/views/WorkflowLogs.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
