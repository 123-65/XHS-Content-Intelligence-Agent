<template>
  <div class="page trace-page">
    <PageHeader title="Agent Trace 控制台" description="最近一次 Agent / Workflow 执行轨迹">
      <el-button :icon="RefreshCw" :loading="loading" @click="loadLatest">刷新</el-button>
    </PageHeader>

    <el-alert v-if="errorMessage" type="error" :title="errorMessage" show-icon :closable="false" />

    <template v-if="latestRun">
      <div class="grid grid-4">
        <MetricCard title="Steps" :value="latestRun.total_steps" :icon="ListChecks" />
        <MetricCard title="LLM Calls" :value="latestRun.llm_call_count" :icon="BrainCircuit" />
        <MetricCard title="Tokens" :value="latestRun.total_token_count" :icon="Coins" />
        <MetricCard title="Latency" :value="`${latestRun.total_latency_ms}ms`" :icon="Clock3" />
      </div>

      <div class="run-band">
        <div>
          <span class="muted">Run #{{ latestRun.id }}</span>
          <h3>{{ latestRun.workflow_name }}</h3>
        </div>
        <div class="run-meta">
          <el-tag :type="statusType(latestRun.status)">{{ latestRun.status }}</el-tag>
          <el-tag v-if="latestRun.stop_reason" type="warning">{{ latestRun.stop_reason }}</el-tag>
          <span>{{ latestRun.agent_type }}</span>
          <span>Account {{ latestRun.account_id || '-' }}</span>
        </div>
      </div>

      <div class="grid trace-layout">
        <el-card shadow="never">
          <template #header>
            <div class="toolbar">
              <strong>Step 时间线</strong>
              <el-tag type="info">{{ latestRun.success_steps }} success / {{ latestRun.failed_steps }} failed</el-tag>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item
              v-for="step in steps"
              :key="step.id"
              :type="statusType(step.status)"
              :timestamp="`${step.latency_ms}ms · ${step.token_count} tokens`"
              placement="top"
            >
              <button class="step-row" :class="{ active: selectedStep?.id === step.id }" @click="selectedStep = step">
                <span class="step-title">{{ step.step_order }}. {{ step.tool_name }}</span>
                <span class="step-tags">
                  <el-tag size="small" :type="statusType(step.status)">{{ step.status }}</el-tag>
                  <el-tag v-if="step.provider_name" size="small" effect="plain">{{ step.provider_name }}</el-tag>
                  <el-tag v-if="step.is_mock" size="small" type="warning">Mock</el-tag>
                  <el-tag v-if="step.fallback_used" size="small" type="danger">Fallback</el-tag>
                </span>
              </button>
            </el-timeline-item>
          </el-timeline>
        </el-card>

        <el-card shadow="never">
          <template #header><strong>Step 调试详情</strong></template>
          <template v-if="selectedStep">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="step_name">{{ selectedStep.step_name }}</el-descriptions-item>
              <el-descriptions-item label="tool_name">{{ selectedStep.tool_name }}</el-descriptions-item>
              <el-descriptions-item label="provider_name">{{ selectedStep.provider_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="is_mock">{{ selectedStep.is_mock ? 'true' : 'false' }}</el-descriptions-item>
              <el-descriptions-item label="prompt">{{ promptLabel(selectedStep) }}</el-descriptions-item>
              <el-descriptions-item label="fallback_used">{{ selectedStep.fallback_used ? 'true' : 'false' }}</el-descriptions-item>
              <el-descriptions-item label="status">{{ selectedStep.status }}</el-descriptions-item>
              <el-descriptions-item label="error">{{ selectedStep.error_message || selectedStep.error_code || '-' }}</el-descriptions-item>
            </el-descriptions>
            <div class="debug-grid">
              <div>
                <h4>tool_input_summary</h4>
                <pre class="code-box">{{ formatJson(selectedStep.tool_input_summary) }}</pre>
              </div>
              <div>
                <h4>tool_output_summary</h4>
                <pre class="code-box">{{ formatJson(selectedStep.tool_output_summary) }}</pre>
              </div>
            </div>
          </template>
          <el-empty v-else description="暂无 Step" />
        </el-card>
      </div>

      <div class="grid trace-tables">
        <el-card shadow="never">
          <template #header><strong>Tool 调用列表</strong></template>
          <el-table :data="latestRun.tool_calls" stripe>
            <el-table-column prop="tool_name" label="tool" min-width="140" />
            <el-table-column prop="status" label="status" width="110" />
            <el-table-column prop="provider_name" label="provider" min-width="130" />
            <el-table-column prop="is_mock" label="mock" width="90" />
            <el-table-column prop="latency_ms" label="latency" width="110" />
            <el-table-column prop="risk_level" label="risk" width="100" />
          </el-table>
        </el-card>

        <el-card shadow="never">
          <template #header><strong>LLM 调用记录</strong></template>
          <el-table :data="latestRun.llm_calls" stripe>
            <el-table-column prop="prompt_key" label="prompt_key" min-width="170" />
            <el-table-column prop="prompt_version" label="version" width="100" />
            <el-table-column prop="provider" label="provider" width="120" />
            <el-table-column prop="model" label="model" min-width="150" />
            <el-table-column prop="is_mock" label="mock" width="90" />
            <el-table-column prop="total_tokens" label="tokens" width="110" />
            <el-table-column prop="estimated_cost" label="cost" width="110" />
          </el-table>
        </el-card>
      </div>

      <div class="grid trace-tables">
        <el-card shadow="never">
          <template #header><strong>Fallback 记录</strong></template>
          <pre class="code-box">{{ formatJson(latestRun.fallback_records) }}</pre>
        </el-card>
        <el-card shadow="never">
          <template #header><strong>错误原因</strong></template>
          <pre class="code-box">{{ formatJson(latestRun.errors) }}</pre>
        </el-card>
      </div>
    </template>

    <el-empty v-else-if="!loading" description="暂无 AgentRun" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { BrainCircuit, Clock3, Coins, ListChecks, RefreshCw } from 'lucide-vue-next'
import MetricCard from '@/components/MetricCard.vue'
import PageHeader from '@/components/PageHeader.vue'
import { getLatestDeveloperRun, getLatestDeveloperSteps } from '@/api/developerTrace'
import type { DeveloperAgentRunDetail, DeveloperAgentStepTrace } from '@/types/developerTrace'

const latestRun = ref<DeveloperAgentRunDetail | null>(null)
const selectedStep = ref<DeveloperAgentStepTrace | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const steps = computed(() => latestRun.value?.steps || [])

const loadLatest = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const [runResponse, stepsResponse] = await Promise.all([getLatestDeveloperRun(), getLatestDeveloperSteps()])
    latestRun.value = { ...runResponse.data, steps: stepsResponse.data }
    selectedStep.value = stepsResponse.data[0] || null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载 Trace 失败'
    latestRun.value = null
    selectedStep.value = null
  } finally {
    loading.value = false
  }
}

const statusType = (status: string) => {
  if (status === 'SUCCESS') return 'success'
  if (status === 'RUNNING') return 'primary'
  if (status === 'FALLBACK_USED' || status === 'REQUIRES_CONFIRMATION') return 'warning'
  return 'danger'
}

const promptLabel = (step: DeveloperAgentStepTrace) => {
  return [step.prompt_key, step.prompt_version].filter(Boolean).join(' · ') || '-'
}

const formatJson = (value: unknown) => JSON.stringify(value || {}, null, 2)

onMounted(loadLatest)
</script>

<style scoped>
.trace-page {
  gap: 18px;
}

.run-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  padding: 16px 18px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.run-band h3 {
  margin: 4px 0 0;
  font-size: 18px;
  letter-spacing: 0;
}

.run-meta,
.step-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.run-meta span {
  color: #64748b;
  font-size: 13px;
}

.trace-layout {
  grid-template-columns: minmax(360px, 0.82fr) minmax(520px, 1.18fr);
  align-items: start;
}

.trace-tables {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.step-row {
  display: flex;
  width: 100%;
  min-height: 48px;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #111827;
  cursor: pointer;
  text-align: left;
}

.step-row.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.step-title {
  min-width: 0;
  overflow: hidden;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.debug-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.debug-grid h4 {
  margin: 0 0 8px;
  font-size: 13px;
}
</style>

