<template>
  <div class="chat-page">
    <header class="chat-header">
      <div>
        <p class="eyebrow">UNIFIED AGENT</p>
        <h1>Agent 对话</h1>
        <span>{{ conversationLabel }}</span>
      </div>
      <div class="header-controls">
        <el-select v-model="selectedAccount" :loading="accountsLoading" placeholder="选择账号" @change="onAccountChange">
          <el-option v-for="account in accounts" :key="account.id" :label="account.account_name" :value="account.id" />
        </el-select>
        <el-button v-if="store.active_run_ref" text type="primary" @click="router.push(`/agent/runs/${store.active_run_ref}`)">Run 详情</el-button>
        <el-tag :type="statusType" effect="plain">{{ statusText }}</el-tag>
      </div>
    </header>

    <main ref="messagePane" class="messages">
      <div v-if="store.history_has_more" class="load-earlier"><el-button :loading="store.history_loading" text @click="loadEarlier">加载更早消息</el-button></div>
      <div v-if="store.history_loading" class="history-loading"><el-skeleton :rows="3" animated /></div>
      <div v-else-if="!store.messages.length" class="welcome">
        <div class="welcome-mark">✦</div>
        <h2>你想先解决什么？</h2>
        <p>直接描述研究、策略、内容创作或复盘任务，Agent 会自行决定如何执行。</p>
      </div>

      <article v-for="message in store.messages" :key="message.id" class="message" :class="message.role.toLowerCase()">
        <div class="avatar">{{ message.role === 'USER' ? '你' : message.role === 'ASSISTANT' ? 'AI' : '·' }}</div>
        <div class="message-content">
          <p>{{ message.content }}</p>
          <div v-if="message.warnings?.length" class="warnings">
            <span v-for="warning in message.warnings" :key="warning">{{ warning }}</span>
          </div>
          <div v-if="message.artifacts?.length" class="artifact-cards">
            <section v-for="artifact in message.artifacts" :key="`${artifact.type}-${artifact.id}`" class="artifact-card">
              <div class="artifact-icon">◇</div>
              <div><small>{{ artifactLabel(artifact.type) }}</small><strong>{{ artifactLabel(artifact.type) }} #{{ artifact.id }}</strong><span>已生成可用业务产物</span></div>
              <el-button v-if="store.artifactRoute(artifact)" text type="primary" @click="openArtifact(artifact)">查看详情 →</el-button>
            </section>
          </div>
        </div>
      </article>

      <div v-if="store.is_sending" class="processing"><span class="pulse"></span>Agent 正在处理</div>

      <section v-if="store.pending_interaction" class="pending-card">
        <small>{{ store.pending_interaction.type === 'CONFIRMATION' ? '请确认后继续' : '需要补充信息' }}</small>
        <strong>{{ pendingPrompt }}</strong>
        <div v-if="store.pending_interaction.required_fields.length" class="missing-fields">
          <span>还需要：</span><el-tag v-for="field in store.pending_interaction.required_fields" :key="field">{{ fieldLabel(field) }}</el-tag>
        </div>
        <div v-if="store.pending_interaction.options.length" class="options">
          <el-tag v-for="option in store.pending_interaction.options" :key="option" @click="draftText = option">{{ option }}</el-tag>
        </div>
        <el-alert v-if="store.pending_interaction.type === 'CONFIRMATION'" title="当前修改确认能力尚未接入" type="warning" :closable="false" show-icon />
      </section>
    </main>

    <footer class="composer">
      <section v-if="store.workspace_context_display || workspaceLabel" class="context-card">
        <div><small>当前工作对象</small><strong>{{ store.workspace_context_display?.title || workspaceLabel }}</strong><span>{{ store.workspace_context_display?.type || '业务对象' }}<template v-if="store.workspace_context_display?.version"> · {{ store.workspace_context_display.version }}</template></span></div>
        <div class="context-actions"><el-button v-if="store.workspace_context_display" text type="primary" @click="router.push(store.workspace_context_display.detail_route)">查看详情</el-button><el-button text @click="store.setWorkspaceSelection({})">清除选择</el-button></div>
      </section>
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" :closable="false" show-icon>
        <el-button v-if="store.retry_state" size="small" @click="retry">使用原 request id 重试</el-button>
      </el-alert>
      <el-collapse v-if="technicalError" class="technical-details"><el-collapse-item title="技术详情"><code>{{ technicalError }}</code></el-collapse-item></el-collapse>
      <el-input v-model="draftText" type="textarea" :autosize="{ minRows: 2, maxRows: 5 }" resize="none" placeholder="告诉 Agent 你想做什么…" @keydown="handleComposerKeydown" />
      <div class="composer-tools">
        <div>
          <el-button text @click="materialsVisible = !materialsVisible">＋ 添加材料</el-button>
          <span>Enter 发送 · Shift + Enter 换行</span>
        </div>
        <el-button type="primary" :loading="store.is_sending" :disabled="!canSend" @click="send">发送</el-button>
      </div>
      <div v-if="materialsVisible" class="materials">
        <div class="material-field">
          <label>小红书笔记链接 <el-tag size="small">{{ noteUrls.length }}/20</el-tag></label>
          <el-input v-model="noteUrlsText" type="textarea" :rows="3" placeholder="每行粘贴一个笔记链接，例如 /explore/..." />
          <small>用于本轮研究材料采集；支持换行、空格或逗号分隔，自动去重。</small>
        </div>
        <div class="material-field">
          <label>小红书账号主页链接 <el-tag size="small">{{ profileUrls.length }}/20</el-tag></label>
          <el-input v-model="profileUrlsText" type="textarea" :rows="3" placeholder="每行粘贴一个账号主页链接，例如 /user/profile/..." />
          <small>用于本轮账号材料采集；仅接受公开 Profile URL。</small>
        </div>
        <el-alert v-if="materialsError" :title="materialsError" type="warning" :closable="false" show-icon />
        <div v-if="materialCount" class="material-summary">
          <span>发送时将附带 {{ noteUrls.length }} 个笔记链接、{{ profileUrls.length }} 个账号链接</span>
          <el-button text type="danger" @click="clearMaterials">清空材料</el-button>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAccountProfiles, type AccountProfileResponse } from '@/api/account'
import { useAgentChatStore } from '@/stores/agentChat'
import type { ArtifactRef, ArtifactType } from '@/types/unifiedAgent'
import { statusLabel } from '@/utils/presentation'

const route = useRoute()
const router = useRouter()
const store = useAgentChatStore()
const accounts = ref<AccountProfileResponse[]>([])
const accountsLoading = ref(false)
const selectedAccount = ref<number | null>(store.account_ref)
const draftText = ref('')
const noteUrlsText = ref('')
const profileUrlsText = ref('')
const materialsVisible = ref(false)
const errorMessage = ref('')
const technicalError = ref('')
const messagePane = ref<HTMLElement | null>(null)

const splitUrls = (value: string) => [...new Set(value.split(/[\s,，]+/).map(item => item.trim()).filter(Boolean))]
const noteUrls = computed(() => splitUrls(noteUrlsText.value))
const profileUrls = computed(() => splitUrls(profileUrlsText.value))
const materialCount = computed(() => noteUrls.value.length + profileUrls.value.length)
const isHttpUrl = (value: string) => { try { const parsed = new URL(value); return ['http:', 'https:'].includes(parsed.protocol) } catch { return false } }
const isXhsHost = (value: string) => { try { const host = new URL(value).hostname.toLowerCase(); return host === 'xiaohongshu.com' || host.endsWith('.xiaohongshu.com') || host === 'xhslink.com' || host === 'www.xhslink.com' } catch { return false } }
const isXhsNoteUrl = (value: string) => {
  if (!isHttpUrl(value) || !isXhsHost(value)) return false
  const parsed = new URL(value)
  return ['xhslink.com', 'www.xhslink.com'].includes(parsed.hostname.toLowerCase())
    ? Boolean(parsed.pathname.replace(/\//g, ''))
    : parsed.pathname.startsWith('/explore/') || parsed.pathname.startsWith('/discovery/item/')
}
const materialsError = computed(() => {
  if (noteUrls.value.length > 20 || profileUrls.value.length > 20) return '每类材料最多提交 20 个链接'
  if (noteUrls.value.some(url => !isXhsNoteUrl(url))) return '笔记材料必须是小红书 /explore/...、/discovery/item/... 或 xhslink 链接'
  if (profileUrls.value.some(url => !isHttpUrl(url) || !isXhsHost(url) || !new URL(url).pathname.startsWith('/user/profile/'))) return '账号材料必须是小红书 /user/profile/... 主页链接'
  return ''
})
const canSend = computed(() => Boolean(selectedAccount.value && draftText.value.trim() && !materialsError.value && !store.is_sending))
const conversationLabel = computed(() => store.conversation_id ? `Conversation #${store.conversation_id}` : '新对话将由首条消息创建')
const statusText = computed(() => store.is_sending ? '处理中' : store.active_status ? statusLabel(store.active_status) : '就绪')
const statusType = computed(() => store.active_status === 'FAILED' ? 'danger' : store.active_status === 'PARTIAL_SUCCESS' ? 'warning' : store.active_status === 'SUCCESS' ? 'success' : 'info')
const workspaceLabel = computed(() => {
  const entry = Object.entries(store.workspace_selection)[0]
  return entry ? `${entry[0].replace('_ref', '').toUpperCase()}:${entry[1]}` : ''
})
const fieldLabels: Record<string, string> = { research_material: '小红书账号或笔记链接', note_urls: '小红书笔记链接', profile_urls: '小红书账号主页链接', evidence_refs: '可引用的研究材料', published_note_ref: '已发布内容', strategy_ref: '关联策略', opportunity_ref: '内容机会' }
const fieldLabel = (value: string) => fieldLabels[value] || '必要信息'
const pendingPrompt = computed(() => {
  const pending = store.pending_interaction
  if (!pending) return ''
  if (pending.required_fields.length) return `请补充${pending.required_fields.map(fieldLabel).join('、')}，然后继续发送。`
  return pending.type === 'CONFIRMATION' ? '请确认是否继续执行当前操作。' : '请补充完成任务所需的信息。'
})
const labels: Record<ArtifactType, string> = {
  RESEARCH: '研究报告', CONTENT_STRATEGY: '内容策略', CONTENT_OPPORTUNITY: '内容机会',
  DRAFT: '草稿', DRAFT_REVIEW: '草稿评审', POST_PUBLISH_REVIEW: '发布复盘', STRATEGY_CANDIDATE: '策略候选'
}
const artifactLabel = (type: ArtifactType) => labels[type]

const onAccountChange = (value: number) => {
  store.switchAccount(value)
  router.replace('/agent/chat')
}
const clearMaterials = () => {
  noteUrlsText.value = ''
  profileUrlsText.value = ''
}
const handleComposerKeydown = (event: KeyboardEvent) => {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  if (canSend.value) void send()
}
const send = async () => {
  const text = draftText.value.trim()
  if (!text || !selectedAccount.value) return
  errorMessage.value = ''
  technicalError.value = ''
  draftText.value = ''
  try {
    await store.sendNewTurn(text, { note_urls: noteUrls.value, profile_urls: profileUrls.value })
    clearMaterials()
    materialsVisible.value = false
    if (store.conversation_id) await router.replace(`/agent/chat/${store.conversation_id}`)
  } catch (error) {
    errorMessage.value = '消息发送失败，请检查输入或稍后重试。'
    technicalError.value = error instanceof Error ? error.message : String(error)
  }
}
const retry = async () => {
  errorMessage.value = ''
  technicalError.value = ''
  try { await store.retryLastTurn() } catch (error) { errorMessage.value = '重试失败，请稍后再试。'; technicalError.value = error instanceof Error ? error.message : String(error) }
}
const openArtifact = (artifact: ArtifactRef) => {
  const target = store.artifactRoute(artifact)
  if (target) router.push(target)
}
const loadEarlier = async () => {
  const pane = messagePane.value
  const oldHeight = pane?.scrollHeight || 0
  await store.loadEarlierMessages()
  await nextTick()
  if (pane) pane.scrollTop += pane.scrollHeight - oldHeight
}

watch(() => store.messages.length, async () => {
  await nextTick()
  if (messagePane.value) messagePane.value.scrollTop = messagePane.value.scrollHeight
})

onMounted(async () => {
  accountsLoading.value = true
  try {
    accounts.value = await getAccountProfiles()
    if (selectedAccount.value && !accounts.value.some(account => account.id === selectedAccount.value)) {
      selectedAccount.value = null
      store.switchAccount(null)
      errorMessage.value = '已保存的账号不可用，请重新选择账号'
    }
    const conversationId = Number(route.params.conversationId)
    if (conversationId > 0) await store.loadRecentConversation(conversationId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载失败'
  } finally { accountsLoading.value = false }
})
</script>

<style scoped>
.chat-page{display:grid;grid-template-rows:auto minmax(360px,1fr) auto;height:calc(100vh - 116px);max-width:1060px;margin:auto;border:1px solid #e5e9f0;border-radius:18px;background:#fff;box-shadow:0 18px 50px #1720330d;overflow:hidden}.chat-header{display:flex;align-items:center;justify-content:space-between;padding:20px 26px;border-bottom:1px solid #edf0f4}.chat-header h1{margin:2px 0 4px;font-size:22px}.chat-header span{color:#7b8495;font-size:12px}.eyebrow{margin:0;color:#4f46e5;font-size:10px;font-weight:800;letter-spacing:.16em}.header-controls{display:flex;align-items:center;gap:12px}.header-controls .el-select{width:200px}.messages{overflow:auto;padding:26px;background:linear-gradient(180deg,#fbfcff,#fff)}.welcome{text-align:center;margin:70px auto;max-width:500px}.welcome-mark{display:grid;place-items:center;width:54px;height:54px;margin:auto;border-radius:18px;background:#eef2ff;color:#4f46e5;font-size:26px}.welcome h2{margin:18px 0 8px}.welcome p{color:#758094;line-height:1.7}.message{display:flex;gap:12px;margin-bottom:22px}.message.user{flex-direction:row-reverse}.avatar{display:grid;place-items:center;width:32px;height:32px;flex:0 0 32px;border-radius:10px;background:#e9edff;color:#4f46e5;font-size:12px;font-weight:700}.user .avatar{background:#172033;color:#fff}.message-content{max-width:76%}.message-content>p{margin:0;padding:12px 15px;border-radius:4px 16px 16px;background:#f1f4f8;line-height:1.7;white-space:pre-wrap}.user .message-content>p{border-radius:16px 4px 16px 16px;background:#4f46e5;color:#fff}.warnings{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.warnings span{padding:5px 9px;border-radius:8px;background:#fff7e6;color:#9a6400;font-size:12px}.artifact-cards{display:grid;gap:9px;margin-top:10px}.artifact-card{display:grid;grid-template-columns:36px 1fr auto;align-items:center;gap:11px;padding:13px;border:1px solid #e2e7f0;border-radius:13px;background:#fff}.artifact-icon{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:#eef2ff;color:#4f46e5}.artifact-card small,.artifact-card strong,.artifact-card span{display:block}.artifact-card small{color:#7d8798;font-size:10px}.artifact-card strong{margin:2px 0;font-size:13px}.artifact-card span{color:#8b94a4;font-size:11px}.processing{display:flex;align-items:center;gap:8px;color:#697386;font-size:13px}.pulse{width:8px;height:8px;border-radius:50%;background:#4f46e5;animation:pulse 1s infinite}.pending-card{display:grid;gap:9px;margin:18px 0 0 44px;padding:15px;border:1px solid #d9defa;border-radius:13px;background:#f7f8ff}.pending-card small{color:#6157d8}.missing-fields,.options{display:flex;align-items:center;flex-wrap:wrap;gap:8px}.options .el-tag{cursor:pointer}.composer{display:grid;gap:10px;padding:15px 22px;border-top:1px solid #edf0f4;background:#fff}.composer-tools,.composer-tools>div,.material-summary,.context-card,.context-actions{display:flex;align-items:center;justify-content:space-between;gap:10px}.composer-tools span,.material-summary span{color:#8b94a4;font-size:11px}.context-card{padding:11px 14px;border:1px solid #c7d2fe;border-radius:12px;background:#f5f7ff}.context-card small,.context-card strong,.context-card span{display:block}.context-card small{color:#6366f1;font-size:10px;font-weight:700}.context-card strong{margin:3px 0;color:#1f2937}.context-card span{color:#6b7280;font-size:12px}.technical-details code{white-space:pre-wrap;color:#64748b;font-size:11px}.materials{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:12px;border-radius:12px;background:#f8fafc}.material-field{display:grid;gap:6px}.material-field label{display:flex;align-items:center;justify-content:space-between;color:#374151;font-size:12px;font-weight:700}.material-field small{color:#8b94a4;line-height:1.5}.materials>.el-alert,.material-summary{grid-column:1/-1}.history-loading{max-width:600px;margin:auto}@keyframes pulse{50%{opacity:.25}}@media(max-width:800px){.chat-page{height:auto;min-height:calc(100vh - 100px)}.chat-header{align-items:flex-start;gap:14px}.header-controls{align-items:flex-end;flex-direction:column}.message-content{max-width:88%}.materials{grid-template-columns:1fr}}
</style>
