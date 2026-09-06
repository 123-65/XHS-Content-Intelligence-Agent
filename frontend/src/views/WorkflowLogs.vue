<template>
  <div class="page">
    <PageHeader title="运行日志" description="展示自研 Workflow Runtime 的 run 与 node 级执行过程。">
      <el-button :icon="RefreshCw">刷新日志</el-button>
    </PageHeader>

    <div class="grid grid-4">
      <MetricCard title="Workflow Runs" :value="workflowRuns.length" :icon="Workflow" />
      <MetricCard title="成功运行" :value="successCount" :icon="CheckCircle2" />
      <MetricCard title="Token 消耗" :value="totalTokens" :icon="Coins" />
      <MetricCard title="估算成本" :value="`¥${totalCost}`" :icon="CircleDollarSign" />
    </div>

    <div class="grid log-grid">
      <el-card shadow="never">
        <template #header><strong>Workflow Run 列表</strong></template>
        <el-table :data="workflowRuns" stripe highlight-current-row @row-click="selectRun">
          <el-table-column prop="type" label="Workflow 类型" min-width="150" />
          <el-table-column prop="experimentName" label="关联实验" min-width="210" />
          <el-table-column label="状态" width="105"><template #default="{ row }"><StatusTag :status="row.status" /></template></el-table-column>
          <el-table-column prop="startedAt" label="开始时间" width="165" />
          <el-table-column prop="endedAt" label="结束时间" width="165" />
          <el-table-column prop="duration" label="总耗时" width="90" />
          <el-table-column prop="errorMessage" label="错误信息" min-width="180" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="toolbar">
            <strong>Node Run 时间线</strong>
            <el-tag type="primary">{{ currentRun.type }}</el-tag>
          </div>
        </template>
        <WorkflowTimeline :nodes="visibleNodes" @select="openNode" />
      </el-card>
    </div>

    <el-drawer v-model="drawerVisible" title="节点详情" size="42%">
      <template v-if="selectedNode">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="节点名称">{{ selectedNode.name }}</el-descriptions-item>
          <el-descriptions-item label="状态"><StatusTag :status="selectedNode.status" /></el-descriptions-item>
          <el-descriptions-item label="耗时">{{ selectedNode.duration }}</el-descriptions-item>
          <el-descriptions-item label="重试次数">{{ selectedNode.retries }}</el-descriptions-item>
          <el-descriptions-item label="prompt_tokens">{{ selectedNode.promptTokens }}</el-descriptions-item>
          <el-descriptions-item label="completion_tokens">{{ selectedNode.completionTokens }}</el-descriptions-item>
          <el-descriptions-item label="total_tokens">{{ selectedNode.totalTokens }}</el-descriptions-item>
          <el-descriptions-item label="estimated_cost">¥{{ selectedNode.estimatedCost }}</el-descriptions-item>
          <el-descriptions-item label="error_message">{{ selectedNode.errorMessage || '无' }}</el-descriptions-item>
        </el-descriptions>
        <h4>input_snapshot</h4>
        <div class="code-box">{{ JSON.stringify(selectedNode.inputSnapshot, null, 2) }}</div>
        <h4>output_snapshot</h4>
        <div class="code-box">{{ JSON.stringify(selectedNode.outputSnapshot, null, 2) }}</div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { CheckCircle2, CircleDollarSign, Coins, RefreshCw, Workflow } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import WorkflowTimeline from '@/components/WorkflowTimeline.vue'
import { nodeRuns, workflowRuns } from '@/mock/workflow'
import type { NodeRun, WorkflowRun } from '@/types/workflow'

const currentRun = ref<WorkflowRun>(workflowRuns[0])
const selectedNode = ref<NodeRun>()
const drawerVisible = ref(false)

const visibleNodes = computed(() => nodeRuns.filter((node) => node.workflowRunId === currentRun.value.id))
const successCount = computed(() => workflowRuns.filter((run) => run.status === 'SUCCESS').length)
const totalTokens = computed(() => visibleNodes.value.reduce((sum, node) => sum + node.tokenUsage, 0))
const totalCost = computed(() => visibleNodes.value.reduce((sum, node) => sum + node.cost, 0).toFixed(2))

const selectRun = (run: WorkflowRun) => {
  currentRun.value = run
}

const openNode = (node: NodeRun) => {
  selectedNode.value = node
  drawerVisible.value = true
}
</script>

<style scoped>
.log-grid {
  grid-template-columns: minmax(0, 1.3fr) minmax(420px, 0.9fr);
}
</style>
