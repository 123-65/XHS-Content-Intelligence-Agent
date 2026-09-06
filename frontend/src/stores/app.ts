import { defineStore } from 'pinia'

export const useAppStore = defineStore('app', {
  state: () => ({
    sidebarCollapsed: false,
    lastWorkflowMessage: '内容实验闭环已完成，策略记忆等待确认更新'
  }),
  actions: {
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    setWorkflowMessage(message: string) {
      this.lastWorkflowMessage = message
    }
  }
})
