<template>
  <div class="page agent-workbench">
    <PageHeader title="Agent 工作台" description="自然语言入口链路 dry-run 预览">
      <el-tag type="info" effect="plain">POST /agent/chat/preview</el-tag>
      <el-tag type="warning" effect="plain">DRY_RUN Only</el-tag>
    </PageHeader>

    <div class="workbench-layout">
      <section class="panel input-panel">
        <div class="panel-header">
          <div>
            <h2>用户自由输入</h2>
            <span>AgentChatRequest</span>
          </div>
          <MessageSquareText :size="20" />
        </div>

        <el-input
          v-model="form.text"
          type="textarea"
          :rows="5"
          resize="none"
          maxlength="240"
          show-word-limit
        />

        <div class="form-grid">
          <label>
            <span>session_id</span>
            <el-input v-model="form.session_id" />
          </label>
          <label>
            <span>account_id</span>
            <el-input-number v-model="form.account_id" :min="1" controls-position="right" />
          </label>
          <label>
            <span>current_target_type</span>
            <el-select v-model="form.current_target_type" clearable>
              <el-option label="DRAFT" value="DRAFT" />
              <el-option label="CONTENT_OPPORTUNITY" value="CONTENT_OPPORTUNITY" />
              <el-option label="PLAN" value="PLAN" />
            </el-select>
          </label>
          <label>
            <span>current_target_id</span>
            <el-input v-model="form.current_target_id" />
          </label>
        </div>

        <div class="example-row">
          <el-button v-for="item in examples" :key="item.label" size="small" @click="applyExample(item)">
            {{ item.label }}
          </el-button>
        </div>

        <div class="action-row">
          <el-button type="primary" :icon="Send" :loading="loading" @click="submitPreview">发送预览</el-button>
          <el-button :icon="FileJson" @click="loadLocalDemo">加载本地 Demo 数据</el-button>
        </div>

        <el-alert v-if="demoLoaded" type="info" title="当前展示本地演示数据，未调用接口" show-icon :closable="false" />
        <el-alert v-if="errorMessage" type="error" :title="errorMessage" show-icon :closable="false" />

        <section v-if="response?.confirmation_card" class="confirmation-panel">
          <div class="panel-header compact">
            <div>
              <h2>{{ response.confirmation_card.title }}</h2>
              <span>{{ response.confirmation_card.confirmation_requirement }}</span>
            </div>
            <ShieldAlert :size="20" />
          </div>
          <p>{{ response.confirmation_card.description }}</p>
          <div class="tag-row">
            <el-tag v-for="flag in response.confirmation_card.risk_flags" :key="flag" type="warning" effect="plain">
              {{ flag }}
            </el-tag>
          </div>
          <pre class="code-box">{{ formatJson(response.confirmation_card.params_preview) }}</pre>
          <el-button type="primary" disabled class="full-button">
            真实执行将在后续阶段接入
          </el-button>
        </section>
      </section>

      <section class="result-panel">
        <div class="status-band panel">
          <div>
            <span class="muted">AgentChatResponse</span>
            <h2>{{ response?.status || '等待输入' }}</h2>
            <p>{{ response?.message || '提交后展示 Router、Planner、Validator、Confirmation 和 dry-run Trace。' }}</p>
          </div>
          <div class="status-tags">
            <el-tag :type="statusType(response?.status)">{{ response?.can_execute ? 'can_execute=true' : 'can_execute=false' }}</el-tag>
            <el-tag v-if="response?.trace_id" type="info" effect="plain">{{ response.trace_id }}</el-tag>
          </div>
        </div>

        <el-steps class="chain-steps" :active="activeStep" finish-status="success" process-status="process" align-center>
          <el-step title="Input" />
          <el-step title="Router" />
          <el-step title="Plan" />
          <el-step title="Validation" />
          <el-step title="Card" />
          <el-step title="Dry-run" />
          <el-step title="Trace" />
        </el-steps>

        <div class="grid result-grid">
          <el-card shadow="never">
            <template #header>
              <div class="toolbar">
                <strong>RouterResult</strong>
                <el-tag :type="statusType(response?.status)" effect="plain">{{ routerIntent }}</el-tag>
              </div>
            </template>
            <el-descriptions v-if="response?.router_result" :column="1" border>
              <el-descriptions-item label="intent">{{ response.router_result.intent }}</el-descriptions-item>
              <el-descriptions-item label="confidence">{{ percent(response.router_result.confidence) }}</el-descriptions-item>
              <el-descriptions-item label="target">{{ response.router_result.target_type }} / {{ response.router_result.target_id || '-' }}</el-descriptions-item>
              <el-descriptions-item label="next_action">{{ response.router_result.next_action || '-' }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="暂无 RouterResult" />
          </el-card>

          <el-card shadow="never">
            <template #header>
              <div class="toolbar">
                <strong>Param / Plan Validation</strong>
                <el-tag :type="validationOk ? 'success' : 'warning'" effect="plain">
                  {{ validationOk ? 'valid' : 'needs attention' }}
                </el-tag>
              </div>
            </template>
            <div class="tag-row">
              <el-tag v-for="item in validationFlags" :key="item" type="warning" effect="plain">{{ item }}</el-tag>
              <el-tag v-if="!validationFlags.length" type="success" effect="plain">NO_RISK_FLAG</el-tag>
            </div>
            <ul class="issue-list" v-if="validationIssues.length">
              <li v-for="issue in validationIssues" :key="`${issue.field}-${issue.message}`">
                <strong>{{ issue.severity }}</strong>
                <span>{{ issue.field || '-' }}</span>
                <p>{{ issue.message }}</p>
              </li>
            </ul>
            <el-empty v-else description="暂无校验问题" />
          </el-card>
        </div>

        <el-card shadow="never">
          <template #header>
            <div class="toolbar">
              <strong>Plan Steps</strong>
              <el-tag effect="plain">{{ response?.plan?.confirmation_requirement || '-' }}</el-tag>
            </div>
          </template>
          <el-table :data="planSteps" stripe>
            <el-table-column prop="step_no" label="#" width="64" />
            <el-table-column prop="action" label="action" min-width="210" />
            <el-table-column prop="allowed_effect" label="effect" width="150" />
            <el-table-column label="params" min-width="220">
              <template #default="{ row }">
                <span class="inline-code">{{ Object.keys(row.input_params || {}).join(', ') || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="state" width="160">
              <template #default="{ row }">
                <el-tag :type="row.can_execute ? 'success' : 'warning'" effect="plain">
                  {{ row.requires_confirmation ? 'confirm' : row.can_execute ? 'ready' : 'blocked' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <div class="grid result-grid">
          <el-card shadow="never">
            <template #header><strong>Execution dry-run</strong></template>
            <el-descriptions v-if="execution" :column="1" border>
              <el-descriptions-item label="mode">{{ execution.mode }}</el-descriptions-item>
              <el-descriptions-item label="status">{{ execution.status }}</el-descriptions-item>
              <el-descriptions-item label="can_execute">{{ execution.can_execute ? 'true' : 'false' }}</el-descriptions-item>
              <el-descriptions-item label="message">{{ execution.message || '-' }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="暂无 dry-run 结果" />
          </el-card>

          <el-card shadow="never">
            <template #header><strong>Entry Trace</strong></template>
            <el-timeline v-if="traceEvents.length">
              <el-timeline-item
                v-for="event in traceEvents"
                :key="`${event.stage}-${event.created_at}`"
                :type="traceEventType(event.stage)"
                :timestamp="event.stage"
                placement="top"
              >
                <div class="trace-item">
                  <strong>{{ event.summary || event.stage }}</strong>
                  <span>{{ event.intent || event.action || event.confirmation_requirement || '-' }}</span>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无 Entry Trace" />
          </el-card>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { FileJson, MessageSquareText, Send, ShieldAlert } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import { previewAgentChat } from '@/api/agentChat'
import { demoAgentRequest, demoAgentResponse } from '@/mock/agentChatDemo'
import type { AgentChatRequest, AgentChatResponse, EntryTraceEvent, ValidationIssue } from '@/types/agentChat'

interface ExampleInput {
  label: string
  text: string
  account_id: number | null
  current_target_type?: string
  current_target_id?: string
}

const examples: ExampleInput[] = [
  { label: '新选题', text: '我想写一篇 27 届双非本科做 Agent 求职的帖子', account_id: null },
  { label: '这个不行', text: '这个不行', account_id: null },
  { label: '标题太 AI', text: '这个标题太 AI 了，换自然一点', account_id: 1, current_target_type: 'DRAFT', current_target_id: '123' },
  { label: '自动发布', text: '直接帮我发布到小红书', account_id: 1 }
]

const form = reactive({
  session_id: `workbench-${Date.now()}`,
  account_id: null as number | null,
  text: examples[0].text,
  current_target_type: '',
  current_target_id: ''
})

const response = ref<AgentChatResponse | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const demoLoaded = ref(false)

const routerIntent = computed(() => response.value?.router_result?.intent || '-')
const planSteps = computed(() => response.value?.plan?.steps || [])
const execution = computed(() => response.value?.metadata.execution || null)
const traceEvents = computed(() => response.value?.metadata.entry_trace?.events || [])
const validationOk = computed(() => Boolean(response.value?.param_validation?.valid && response.value?.plan_validation?.valid))
const validationIssues = computed<ValidationIssue[]>(() => [
  ...(response.value?.param_validation?.issues || []),
  ...(response.value?.plan_validation?.issues || [])
])
const validationFlags = computed(() => {
  const flags = new Set<string>()
  response.value?.router_result?.risk_flags.forEach((item) => flags.add(item))
  response.value?.plan?.risk_flags.forEach((item) => flags.add(item))
  response.value?.plan_validation?.risk_flags.forEach((item) => flags.add(item))
  return Array.from(flags)
})
const activeStep = computed(() => {
  if (!response.value) return 0
  if (!response.value.metadata.entry_trace) return 5
  return 7
})

const applyExample = (item: ExampleInput) => {
  form.text = item.text
  form.account_id = item.account_id
  form.current_target_type = item.current_target_type || ''
  form.current_target_id = item.current_target_id || ''
  demoLoaded.value = false
}

const buildRequest = (): AgentChatRequest => ({
  session_id: form.session_id || `workbench-${Date.now()}`,
  account_id: form.account_id,
  text: form.text,
  input_type: 'TEXT',
  attachments: [],
  context: {},
  current_target_type: form.current_target_type || null,
  current_target_id: form.current_target_id || null
})

const submitPreview = async () => {
  loading.value = true
  errorMessage.value = ''
  demoLoaded.value = false
  try {
    response.value = await previewAgentChat(buildRequest())
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Agent Chat preview 请求失败'
  } finally {
    loading.value = false
  }
}

const loadLocalDemo = () => {
  Object.assign(form, {
    session_id: demoAgentRequest.session_id || `workbench-${Date.now()}`,
    account_id: demoAgentRequest.account_id || null,
    text: demoAgentRequest.text || '',
    current_target_type: demoAgentRequest.current_target_type || '',
    current_target_id: String(demoAgentRequest.current_target_id || '')
  })
  response.value = demoAgentResponse
  errorMessage.value = ''
  demoLoaded.value = true
}

const statusType = (status?: string) => {
  if (status === 'READY_TO_EXECUTE') return 'success'
  if (status === 'WAITING_CONFIRMATION' || status === 'NEED_CLARIFICATION') return 'warning'
  if (status === 'BLOCKED' || status === 'FAILED') return 'danger'
  return 'info'
}

const traceEventType = (stage: EntryTraceEvent['stage']) => {
  if (stage.includes('FAILED') || stage.includes('BLOCKED')) return 'danger'
  if (stage.includes('VALIDATED') || stage.includes('FINISHED')) return 'success'
  return 'primary'
}

const percent = (value: number) => `${Math.round(value * 100)}%`

const formatJson = (value: unknown) => JSON.stringify(value || {}, null, 2)
</script>

<style scoped>
.agent-workbench {
  gap: 18px;
}

.workbench-layout {
  display: grid;
  grid-template-columns: minmax(360px, 420px) minmax(680px, 1fr);
  gap: 16px;
  align-items: start;
}

.input-panel,
.status-band {
  padding: 16px;
}

.input-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-header.compact {
  margin-bottom: 10px;
}

.panel-header h2,
.status-band h2 {
  margin: 0;
  color: #111827;
  font-size: 18px;
  letter-spacing: 0;
}

.panel-header span {
  display: block;
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.form-grid label {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 6px;
}

.form-grid label > span {
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.form-grid :deep(.el-input-number),
.form-grid :deep(.el-select) {
  width: 100%;
}

.example-row,
.tag-row,
.status-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.confirmation-panel {
  padding: 14px;
  border: 1px solid #f59e0b;
  border-radius: 8px;
  background: #fffbeb;
}

.confirmation-panel p,
.status-band p {
  margin: 8px 0 0;
  color: #475569;
  line-height: 1.7;
}

.full-button {
  width: 100%;
  margin-top: 12px;
}

.result-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-band {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.chain-steps {
  padding: 14px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.result-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.issue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 12px 0 0;
  padding: 0;
  list-style: none;
}

.issue-list li {
  padding: 10px 12px;
  border: 1px solid #fed7aa;
  border-radius: 8px;
  background: #fff7ed;
}

.issue-list strong,
.issue-list span {
  margin-right: 8px;
  color: #9a3412;
  font-size: 12px;
}

.issue-list p {
  margin: 6px 0 0;
  color: #374151;
  line-height: 1.6;
}

.inline-code {
  color: #334155;
  font-family: "JetBrains Mono", Consolas, monospace;
  font-size: 12px;
}

.trace-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.trace-item strong,
.trace-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-item span {
  color: #64748b;
  font-size: 12px;
}
</style>
