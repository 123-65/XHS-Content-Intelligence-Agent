import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/agent/workbench' },
  { path: '/agent/workbench', name: 'agentWorkbench', component: () => import('@/views/AgentWorkbench.vue') },
  { path: '/developer/agent-trace', name: 'developerAgentTrace', component: () => import('@/views/DeveloperAgentTrace.vue') }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
