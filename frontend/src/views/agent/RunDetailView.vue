<template><div class="run-page"><el-button text @click="router.back()">← 返回</el-button><el-card v-loading="loading"><template #header><strong>Run {{ runRef }}</strong></template><el-alert v-if="error" :title="error" type="error" :closable="false"/><el-descriptions v-else-if="run" :column="1" border><el-descriptions-item label="Status">{{ run.status }}</el-descriptions-item><el-descriptions-item label="Workflow">{{ run.workflow_name }}</el-descriptions-item><el-descriptions-item label="Checkpoint">{{ run.checkpoint_version }}</el-descriptions-item></el-descriptions></el-card></div></template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAgentRun } from '@/api/unifiedAgent'
import { useAgentChatStore } from '@/stores/agentChat'
import type { AgentRunResponse } from '@/types/unifiedAgent'

const route = useRoute()
const router = useRouter()
const store = useAgentChatStore()
const runRef = String(route.params.runRef)
const loading = ref(true)
const error = ref('')
const run = ref<AgentRunResponse | null>(null)
const controller = new AbortController()

onMounted(async () => {
  if (!store.account_ref) {
    error.value = '请先在 Agent 对话选择账号'
    loading.value = false
    return
  }
  try {
    run.value = await getAgentRun(runRef, store.account_ref, controller.signal)
  } catch (caught) {
    if (!controller.signal.aborted) error.value = store.clearRejectedAccount(caught) ? '账号不可用，请重新选择账号' : caught instanceof Error ? caught.message : 'Run 加载失败'
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => controller.abort())
</script>
<style scoped>.run-page{max-width:900px;margin:auto}.el-card{margin-top:14px}</style>
