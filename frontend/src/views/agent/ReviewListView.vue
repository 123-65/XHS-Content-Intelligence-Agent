<template>
  <AssetListShell
    title="Review"
    description="查看已发布内容的复盘结论与下一轮策略建议。"
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
      <button class="asset-row" @click="router.push({ name: 'agentPublication', params: { publishedNoteRef: item.published_note_ref } })">
        <span>
          <strong>发布后复盘</strong>
          <small>复盘记录 {{ item.ref }} · 绑定已发布内容 {{ item.published_note_ref }} · {{ formatTime(item.created_at) }}</small>
        </span>
        <el-tag>{{ statusLabel(item.result_status || item.status) }}</el-tag>
      </button>
    </template>
  </AssetListShell>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AssetListShell from '@/components/AssetListShell.vue'
import { getReviewList } from '@/api/unifiedAgent'
import { useAgentChatStore } from '@/stores/agentChat'
import type { ReviewSummary } from '@/types/productRead'
import { formatTime, statusLabel } from '@/utils/presentation'

const store = useAgentChatStore()
const router = useRouter()
const items = ref<ReviewSummary[]>([])
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
    const result = await getReviewList(store.account_ref, page, pageSize, controller.signal)
    items.value = result.items
    total.value = result.total
    pageNo.value = result.page_no
  } catch (reason) {
    if ((reason as Error).name !== 'CanceledError') error.value = '复盘列表加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
onBeforeUnmount(() => controller?.abort())
</script>
