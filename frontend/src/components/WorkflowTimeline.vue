<template>
  <el-timeline>
    <el-timeline-item
      v-for="node in nodes"
      :key="node.id"
      :timestamp="`${node.duration} · 重试 ${node.retries}`"
      placement="top"
      :type="timelineType(node.status)"
    >
      <div class="node-card" @click="$emit('select', node)">
        <div class="toolbar">
          <strong>{{ node.name }}</strong>
          <StatusTag :status="node.status" />
        </div>
        <p>{{ node.inputSummary }}</p>
        <p>{{ node.outputSummary }}</p>
        <div class="node-meta">
          <span>Token {{ node.tokenUsage }}</span>
          <span>成本 ¥{{ node.cost.toFixed(2) }}</span>
        </div>
      </div>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import StatusTag from './StatusTag.vue'
import type { NodeRun, RunStatus } from '@/types/workflow'

defineProps<{ nodes: NodeRun[] }>()
defineEmits<{ select: [node: NodeRun] }>()

const timelineType = (status: RunStatus) => {
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'RUNNING') return 'primary'
  return 'info'
}
</script>

<style scoped>
.node-card {
  cursor: pointer;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.node-card:hover {
  border-color: #93c5fd;
}

p {
  margin: 8px 0;
  color: #4b5563;
}

.node-meta {
  display: flex;
  gap: 16px;
  color: #6b7280;
  font-size: 12px;
}
</style>
