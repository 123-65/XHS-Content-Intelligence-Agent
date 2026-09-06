<template>
  <el-tag :type="type" effect="light" round>{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ status: string }>()

const statusMap: Record<string, { label: string; type: '' | 'success' | 'warning' | 'info' | 'danger' | 'primary' }> = {
  SUCCESS: { label: '成功', type: 'success' },
  RUNNING: { label: '进行中', type: 'primary' },
  FAILED: { label: '失败', type: 'danger' },
  PENDING: { label: '待处理', type: 'info' },
  DRAFT: { label: '草稿', type: 'info' },
  READY: { label: '待发布', type: 'warning' },
  PUBLISHED: { label: '已发布', type: 'primary' },
  METRICS_COLLECTED: { label: '已回采', type: 'success' },
  ANALYZED: { label: '已复盘', type: 'success' },
  LOW: { label: '低风险', type: 'success' },
  MEDIUM: { label: '中风险', type: 'warning' },
  HIGH: { label: '高风险', type: 'danger' }
}

const config = computed(() => statusMap[props.status] || { label: props.status, type: 'info' })
const label = computed(() => config.value.label)
const type = computed(() => config.value.type)
</script>
