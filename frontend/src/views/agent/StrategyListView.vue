<template>
  <AssetListShell
    title="Strategy"
    description="由研究结论沉淀的内容策略，可进入详情查看目标、受众与内容机会。"
    :account-ref="store.account_ref"
    :items="items"
    :loading="loading"
    :error="error"
    :page-no="pageNo"
    :page-size="pageSize"
    :total="total"
    @page-change="load"
  >
    <template #default="{ item }">
      <button class="asset-row" @click="router.push({ name: 'agentStrategy', params: { artifactRef: item.ref } })">
        <span><strong>{{ item.goal }}</strong><small>目标受众：{{ item.audience || '暂未说明' }}</small></span>
        <el-tag type="info">来自研究 {{ item.research_ref }}</el-tag>
      </button>
    </template>
  </AssetListShell>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AssetListShell from '@/components/AssetListShell.vue'
import { getStrategyList } from '@/api/unifiedAgent'
import { useAgentChatStore } from '@/stores/agentChat'
import type { StrategySummary } from '@/types/productRead'

const store = useAgentChatStore()
const router = useRouter()
const items = ref<StrategySummary[]>([])
const loading = ref(false)
const error = ref('')
const pageNo = ref(1)
const pageSize = 20
const total = ref(0)
let controller: AbortController | null = null

async function load(page = 1) {
  if (!store.account_ref) return
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const result = await getStrategyList(store.account_ref, page, pageSize, controller.signal)
    items.value = result.items
    total.value = result.total
    pageNo.value = result.page_no
  } catch (reason) {
    if ((reason as Error).name !== 'CanceledError') error.value = '策略列表加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
onBeforeUnmount(() => controller?.abort())
</script>
