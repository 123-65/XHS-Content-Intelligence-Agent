<template>
  <div class="detail-page">
    <el-button text @click="router.push(chatRoute)">← 返回 Agent 对话</el-button>
    <section class="detail-card">
      <p class="eyebrow">{{ kind }}</p>
      <h1>{{ title }}</h1>
      <p class="identity">内部引用：{{ artifactRef }}</p>
      <el-skeleton v-if="loading" :rows="6" animated />
      <el-alert v-else-if="error" :title="error" type="error" :closable="false" show-icon />
      <slot v-else />
      <div v-if="selection && !loading && !error" class="actions">
        <el-button type="primary" @click="selectAndReturn">选择到对话</el-button>
        <span>后续对话将围绕这个{{ selectionLabel || '对象' }}继续</span>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAgentChatStore } from '@/stores/agentChat'
import type { WorkspaceSelection } from '@/types/unifiedAgent'

const props = defineProps<{ kind: string; title: string; artifactRef: number; loading: boolean; error?: string; selection?: WorkspaceSelection; selectionLabel?: string; selectionTitle?: string; selectionVersion?: string }>()
const router = useRouter()
const store = useAgentChatStore()
const chatRoute = computed(() => store.conversation_id ? `/agent/chat/${store.conversation_id}` : '/agent/chat')
const selectAndReturn = async () => {
  if (props.selection) store.setWorkspaceSelection(props.selection, {
    type: props.selectionLabel || props.kind,
    title: props.selectionTitle || props.title,
    version: props.selectionVersion,
    detail_route: router.currentRoute.value.fullPath
  })
  await router.push(chatRoute.value)
}
</script>

<style scoped>
.detail-page{max-width:980px;margin:auto}.detail-card{min-height:480px;margin-top:14px;padding:32px;border:1px solid #e5e9f0;border-radius:18px;background:#fff;box-shadow:0 18px 45px #1720330a}.detail-card h1{margin:5px 0 4px}.identity{margin:0 0 28px;color:#8b94a4;font-size:12px}.eyebrow{margin:0;color:#4f46e5;font-size:11px;font-weight:800;letter-spacing:.14em}.actions{display:flex;align-items:center;gap:14px;margin-top:24px;padding-top:20px;border-top:1px solid #edf0f4}.actions span{color:#7b8495;font-size:12px}
</style>
