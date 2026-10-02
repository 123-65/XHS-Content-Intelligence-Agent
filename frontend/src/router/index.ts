import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/agent/chat' },
  { path: '/agent/workbench', redirect: '/agent/chat' },
  { path: '/agent/chat/:conversationId?', name: 'agentChat', component: () => import('@/views/AgentChatView.vue') },
  { path: '/agent/research', name: 'agentResearchList', component: () => import('@/views/agent/ResearchListView.vue') },
  { path: '/agent/research/:artifactRef', name: 'agentResearch', component: () => import('@/views/agent/ResearchDetailView.vue') },
  { path: '/agent/strategy', name: 'agentStrategyList', component: () => import('@/views/agent/StrategyListView.vue') },
  { path: '/agent/strategy/:artifactRef', name: 'agentStrategy', component: () => import('@/views/agent/StrategyDetailView.vue') },
  { path: '/agent/draft', name: 'agentDraftList', component: () => import('@/views/agent/DraftListView.vue') },
  { path: '/agent/draft/:draftRef', name: 'agentDraft', component: () => import('@/views/agent/DraftDetailView.vue') },
  { path: '/agent/publications', name: 'agentPublicationList', component: () => import('@/views/agent/PublicationListView.vue') },
  { path: '/agent/publication/:publishedNoteRef', name: 'agentPublication', component: () => import('@/views/agent/PublicationDetailView.vue') },
  { path: '/agent/reviews', name: 'agentReviewList', component: () => import('@/views/agent/ReviewListView.vue') },
  { path: '/agent/runs/:runRef', name: 'agentRun', component: () => import('@/views/agent/RunDetailView.vue') },
  { path: '/developer/agent-trace', name: 'developerAgentTrace', component: () => import('@/views/DeveloperAgentTrace.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
