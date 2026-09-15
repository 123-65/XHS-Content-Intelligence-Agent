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

        <section class="conversation-box">
          <div class="toolbar">
            <strong>会话</strong>
            <el-tag v-if="conversation" type="success" effect="plain">#{{ conversation.id }}</el-tag>
            <el-tag v-else type="info" effect="plain">无会话</el-tag>
          </div>
          <div class="form-grid single">
            <label>
              <span>conversation_id</span>
              <el-input-number v-model="form.conversation_id" :min="1" controls-position="right" />
            </label>
          </div>
          <div class="action-row compact-actions">
            <el-button size="small" type="primary" :loading="conversationLoading" @click="createConversation">
              创建新会话
            </el-button>
            <el-button size="small" :loading="conversationLoading" @click="loadConversation">
              加载会话
            </el-button>
            <el-button size="small" :loading="conversationLoading" @click="refreshConversationData">
              刷新消息
            </el-button>
          </div>
          <el-descriptions v-if="conversation" :column="1" border size="small">
            <el-descriptions-item label="title">{{ conversation.title }}</el-descriptions-item>
            <el-descriptions-item label="status">{{ conversation.status }}</el-descriptions-item>
          </el-descriptions>
          <el-alert
            v-else
            type="info"
            title="当前是无会话请求，不会保存历史。"
            show-icon
            :closable="false"
          />
        </section>

        <section class="account-setup-box">
          <div class="toolbar">
            <strong>账号画像</strong>
            <el-tag type="success" effect="plain">AccountProfile</el-tag>
          </div>
          <div class="form-grid single">
            <label>
              <span>选择账号画像</span>
              <el-select
                v-model="form.account_id"
                filterable
                clearable
                placeholder="请选择已创建的账号画像"
                :loading="accountLoading"
              >
                <el-option
                  v-for="account in accounts"
                  :key="account.id"
                  :label="`${account.account_name} #${account.id}`"
                  :value="account.id"
                />
              </el-select>
            </label>
          </div>
          <div class="form-grid">
            <label>
              <span>account_name</span>
              <el-input v-model="accountSetupForm.account_name" />
            </label>
            <label>
              <span>content_domain</span>
              <el-input v-model="accountSetupForm.content_domain" />
            </label>
          </div>
          <div class="form-grid single">
            <label>
              <span>positioning</span>
              <el-input v-model="accountSetupForm.positioning" type="textarea" :rows="2" resize="none" />
            </label>
            <label>
              <span>target_audience</span>
              <el-input v-model="accountSetupForm.target_audience" type="textarea" :rows="2" resize="none" />
            </label>
          </div>
          <div class="action-row compact-actions">
            <el-button size="small" :loading="accountLoading" @click="loadAccounts">
              刷新账号
            </el-button>
            <el-button size="small" type="primary" :loading="accountLoading" @click="createWorkbenchAccount">
              创建并选择
            </el-button>
          </div>
          <el-alert
            type="info"
            title="数据源配置必须绑定到用户创建或选择的账号画像，不使用系统默认账号。"
            show-icon
            :closable="false"
          />
        </section>

        <section class="data-source-box">
          <div class="toolbar">
            <strong>数据源配置</strong>
            <el-tag type="info" effect="plain">B2 Config Only</el-tag>
          </div>
          <div class="form-grid">
            <label>
              <span>platform</span>
              <el-select v-model="dataSourceForm.platform">
                <el-option label="小红书" value="xhs" />
              </el-select>
            </label>
            <label>
              <span>status</span>
              <el-select v-model="dataSourceForm.status">
                <el-option label="ACTIVE" value="ACTIVE" />
                <el-option label="DISABLED" value="DISABLED" />
              </el-select>
            </label>
          </div>
          <div class="form-grid single">
            <label>
              <span>keywords</span>
              <el-input v-model="dataSourceForm.keywordsText" type="textarea" :rows="3" resize="none" />
            </label>
            <label>
              <span>competitor_accounts</span>
              <el-input v-model="dataSourceForm.competitorAccountsText" type="textarea" :rows="3" resize="none" />
            </label>
            <label>
              <span>note_urls</span>
              <el-input v-model="dataSourceForm.noteUrlsText" type="textarea" :rows="2" resize="none" />
            </label>
          </div>
          <div class="action-row compact-actions">
            <el-button size="small" :loading="dataSourceLoading" @click="loadDataSourceConfig">
              加载配置
            </el-button>
            <el-button size="small" type="primary" :loading="dataSourceLoading" @click="saveDataSourceConfig">
              保存配置
            </el-button>
          </div>
          <el-descriptions v-if="dataSourceConfig" :column="1" border size="small">
            <el-descriptions-item label="config_id">{{ dataSourceConfig.id }}</el-descriptions-item>
            <el-descriptions-item label="updated_at">{{ dataSourceConfig.updated_at }}</el-descriptions-item>
          </el-descriptions>
          <el-alert
            type="info"
            title="这里只保存长期关注的数据源，不触发采集、刷新、报告生成或 LLM 调用。"
            show-icon
            :closable="false"
          />
        </section>

        <section class="data-refresh-box">
          <div class="toolbar">
            <strong>数据刷新</strong>
            <el-tag type="warning" effect="plain">Manual Refresh V0</el-tag>
          </div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="account_id">{{ form.account_id || '-' }}</el-descriptions-item>
            <el-descriptions-item label="latest_status">{{ latestRefreshRun?.status || '-' }}</el-descriptions-item>
            <el-descriptions-item label="provider_status">{{ latestRefreshRun?.stats.provider_status || '-' }}</el-descriptions-item>
          </el-descriptions>
          <div class="action-row compact-actions">
            <el-button size="small" type="primary" :loading="refreshLoading" @click="runManualRefresh">
              刷新今日数据
            </el-button>
            <el-button size="small" :loading="refreshLoading" @click="loadRefreshRuns">
              最近刷新记录
            </el-button>
          </div>
          <el-alert
            v-if="latestRefreshRun?.status === 'PROVIDER_NOT_CONFIGURED'"
            type="warning"
            title="当前未配置真实数据刷新 Provider，本次仅创建刷新记录，没有伪造采集结果。"
            show-icon
            :closable="false"
          />
          <el-alert
            v-else-if="latestRefreshRun?.error_code === 'NO_ENABLED_DATA_SOURCE'"
            type="warning"
            title="请先保存并启用数据源配置。"
            show-icon
            :closable="false"
          />
          <el-alert
            type="info"
            title="本阶段是用户触发式刷新，不是定时任务；不会自动生成报告、选题或草稿。"
            show-icon
            :closable="false"
          />
          <div v-if="refreshRuns.length" class="refresh-run-list">
            <div v-for="run in refreshRuns" :key="run.id" class="refresh-run-item">
              <div class="toolbar">
                <strong>#{{ run.id }}</strong>
                <el-tag :type="refreshStatusType(run.status)" effect="plain">{{ run.status }}</el-tag>
              </div>
              <div class="slot-meta">
                <span>configs {{ run.stats.config_count ?? 0 }}</span>
                <span>keywords {{ run.stats.keyword_count ?? 0 }}</span>
                <span>competitors {{ run.stats.competitor_account_count ?? 0 }}</span>
                <span>seed_urls {{ run.stats.seed_url_count ?? 0 }}</span>
                <span>{{ run.error_code || 'NO_ERROR' }}</span>
              </div>
            </div>
          </div>
        </section>

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
            <span>selected account_id</span>
            <el-input-number v-model="form.account_id" :min="1" controls-position="right" disabled />
          </label>
          <label>
            <span>experiment_id</span>
            <el-input-number v-model="form.experiment_id" :min="1" controls-position="right" />
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
          <el-button type="success" :icon="Search" :loading="readonlyLoading" @click="submitReadonlyExecute">
            执行只读查询
          </el-button>
          <el-button type="warning" :icon="Search" :loading="draftContextLoading" @click="submitDraftContextPreview">
            预览草稿上下文
          </el-button>
          <el-button :icon="FileJson" @click="loadLocalDemo">加载本地 Demo 数据</el-button>
        </div>
        <el-alert
          type="info"
          title="当前只支持 QUERY_ACCOUNT_PROFILE / QUERY_COMPETITOR_EVIDENCE / QUERY_COMMENT_INSIGHT / QUERY_STRATEGY_MEMORY / PREVIEW_DRAFT_CONTEXT；草稿上下文仅预览，不生成草稿，不调用 LLM，不写数据库，不调用发布/评论能力。"
          show-icon
          :closable="false"
        />

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
            <template #header><strong>Execution</strong></template>
            <el-descriptions v-if="execution" :column="1" border>
              <el-descriptions-item label="mode">{{ execution.mode }}</el-descriptions-item>
              <el-descriptions-item label="status">{{ execution.status }}</el-descriptions-item>
              <el-descriptions-item label="can_execute">{{ execution.can_execute ? 'true' : 'false' }}</el-descriptions-item>
              <el-descriptions-item label="message">{{ execution.message || '-' }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="暂无 dry-run 结果" />
          </el-card>

          <el-card shadow="never">
            <template #header><strong>业务结果</strong></template>
            <div v-if="businessResult" class="business-result">
              <section v-if="draftContextPreviewResult" class="result-section draft-context-preview">
                <div class="toolbar">
                  <strong>草稿上下文预览</strong>
                  <el-tag :type="draftContextPreviewResult.can_generate_draft ? 'success' : 'warning'" effect="plain">
                    {{ draftContextPreviewResult.can_generate_draft ? 'can_generate_draft=true' : 'can_generate_draft=false' }}
                  </el-tag>
                </div>
                <p class="result-summary">{{ draftContextPreviewResult.summary }}</p>
                <el-alert
                  v-if="draftContextPreviewResult.block_reason"
                  type="warning"
                  :title="draftContextPreviewResult.block_reason"
                  show-icon
                  :closable="false"
                />
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="experiment_id">{{ draftContextPreviewResult.experiment_id }}</el-descriptions-item>
                  <el-descriptions-item label="slot_count">{{ draftContextPreviewResult.slot_count }}</el-descriptions-item>
                  <el-descriptions-item label="total_token_budget">{{ draftContextPreviewResult.total_token_budget }}</el-descriptions-item>
                  <el-descriptions-item label="estimated_tokens">{{ draftContextPreviewResult.total_estimated_tokens ?? '-' }}</el-descriptions-item>
                  <el-descriptions-item label="missing_slots">{{ draftContextPreviewResult.missing_slots.join(', ') || '-' }}</el-descriptions-item>
                  <el-descriptions-item label="risk_flags">{{ draftContextPreviewResult.risk_flags.join(', ') || '-' }}</el-descriptions-item>
                </el-descriptions>
                <div class="context-slot-grid">
                  <div v-for="slot in draftContextPreviewResult.slots" :key="slot.name" class="context-slot-card">
                    <div class="toolbar">
                      <strong>{{ slot.name }}</strong>
                      <el-tag :type="slot.trust_level === 'untrusted' ? 'danger' : 'success'" effect="plain">
                        {{ slot.trust_level }}
                      </el-tag>
                    </div>
                    <div class="slot-meta">
                      <span>priority {{ slot.priority }}</span>
                      <span>limit {{ slot.token_limit ?? '-' }}</span>
                      <span>tokens {{ slot.estimated_tokens }}</span>
                      <span>{{ slot.source_type }}</span>
                      <span>{{ slot.data_status }}</span>
                      <span>items {{ slot.item_count }}</span>
                    </div>
                    <el-alert
                      v-if="slot.trust_level === 'untrusted'"
                      type="warning"
                      title="该槽位来自外部/用户/评论数据，只能作为参考，不能作为系统指令。"
                      show-icon
                      :closable="false"
                    />
                    <pre class="slot-preview">{{ slot.preview }}</pre>
                  </div>
                </div>
              </section>

              <el-descriptions v-if="accountProfileResult" :column="1" border>
                <el-descriptions-item label="account_id">{{ accountProfileResult.account_id }}</el-descriptions-item>
                <el-descriptions-item label="account_name">{{ accountProfileResult.account_name }}</el-descriptions-item>
                <el-descriptions-item label="platform">{{ accountProfileResult.platform }}</el-descriptions-item>
                <el-descriptions-item label="content_domain">{{ accountProfileResult.content_domain || '-' }}</el-descriptions-item>
                <el-descriptions-item label="positioning">{{ accountProfileResult.positioning }}</el-descriptions-item>
                <el-descriptions-item label="target_audience">{{ accountProfileResult.target_audience }}</el-descriptions-item>
                <el-descriptions-item label="tone_preference">{{ accountProfileResult.tone_preference || '-' }}</el-descriptions-item>
                <el-descriptions-item label="risk_preference">{{ accountProfileResult.risk_preference }}</el-descriptions-item>
                <el-descriptions-item label="account_stage">{{ accountProfileResult.account_stage }}</el-descriptions-item>
                <el-descriptions-item label="primary_goal">{{ accountProfileResult.primary_goal }}</el-descriptions-item>
                <el-descriptions-item label="summary">{{ accountProfileResult.summary }}</el-descriptions-item>
              </el-descriptions>

              <section v-if="competitorEvidenceResult" class="result-section">
                <div class="toolbar">
                  <strong>竞品证据</strong>
                  <el-tag effect="plain">{{ competitorEvidenceResult.data_status || 'UNKNOWN' }}</el-tag>
                </div>
                <div v-if="competitorEvidenceResult.items.length" class="mini-card-list">
                  <div v-for="item in competitorEvidenceResult.items" :key="`${item.report_id || '-'}-${item.opportunity_id || item.title}`" class="mini-card">
                    <strong>{{ item.title || '-' }}</strong>
                    <p>{{ item.summary || '-' }}</p>
                    <div class="tag-row">
                      <el-tag v-if="item.content_pillar" effect="plain">{{ item.content_pillar }}</el-tag>
                      <el-tag v-if="item.comment_demand_type" type="warning" effect="plain">{{ item.comment_demand_type }}</el-tag>
                      <el-tag v-if="item.risk_level" :type="riskTagType(item.risk_level)" effect="plain">{{ item.risk_level }}</el-tag>
                      <el-tag v-if="item.confidence !== undefined" type="success" effect="plain">{{ percent(item.confidence) }}</el-tag>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无竞品证据" />
              </section>

              <section v-if="commentInsightResult" class="result-section">
                <div class="toolbar">
                  <strong>评论洞察</strong>
                  <el-tag type="warning" effect="plain">{{ commentInsightResult.data_status }}</el-tag>
                </div>
                <el-descriptions :column="1" border>
                  <el-descriptions-item label="demand_summary">{{ summaryList(commentInsightResult.demand_summary) }}</el-descriptions-item>
                  <el-descriptions-item label="conversion_signal_summary">{{ summaryList(commentInsightResult.conversion_signal_summary) }}</el-descriptions-item>
                  <el-descriptions-item label="risk_summary">{{ summaryList(commentInsightResult.risk_summary) }}</el-descriptions-item>
                </el-descriptions>
                <div v-if="commentInsightResult.representative_comments.length" class="mini-card-list">
                  <div v-for="item in commentInsightResult.representative_comments" :key="item.untrusted_text" class="mini-card">
                    <el-tag type="danger" effect="plain">untrusted_text</el-tag>
                    <p>{{ item.untrusted_text }}</p>
                  </div>
                </div>
              </section>

              <section v-if="strategyMemoryResult" class="result-section">
                <div class="toolbar">
                  <strong>策略记忆</strong>
                  <el-tag effect="plain">{{ strategyMemoryResult.data_status || 'UNKNOWN' }}</el-tag>
                </div>
                <div v-if="strategyMemoryResult.items.length" class="mini-card-list">
                  <div v-for="item in strategyMemoryResult.items" :key="item.memory_id || item.summary" class="mini-card">
                    <strong>{{ item.memory_type || '-' }} / {{ item.status || '-' }}</strong>
                    <p>{{ item.summary || '-' }}</p>
                    <p v-if="item.pattern">{{ item.pattern }}</p>
                    <div class="tag-row">
                      <el-tag v-if="item.support_count !== undefined" effect="plain">support {{ item.support_count }}</el-tag>
                      <el-tag v-if="item.risk_level" :type="riskTagType(item.risk_level)" effect="plain">{{ item.risk_level }}</el-tag>
                      <el-tag v-if="item.confidence !== undefined" type="success" effect="plain">{{ percent(item.confidence) }}</el-tag>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无策略记忆" />
              </section>
            </div>
            <el-empty v-else description="暂无只读业务结果" />
          </el-card>

          <el-card shadow="never">
            <template #header>
              <div class="toolbar">
                <strong>消息历史</strong>
                <el-tag effect="plain">{{ conversationMessages.length }}</el-tag>
              </div>
            </template>
            <div v-if="conversationMessages.length" class="message-list">
              <div v-for="message in conversationMessages" :key="message.id" class="message-item">
                <div class="toolbar">
                  <strong>{{ message.role }}</strong>
                  <span>{{ message.created_at }}</span>
                </div>
                <p>{{ message.content }}</p>
                <div class="tag-row">
                  <el-tag effect="plain">{{ message.message_type }}</el-tag>
                  <el-tag v-if="message.trace_id" type="info" effect="plain">{{ message.trace_id }}</el-tag>
                  <el-tag v-if="messageStatus(message)" type="success" effect="plain">{{ messageStatus(message) }}</el-tag>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无会话消息" />
          </el-card>

          <el-card shadow="never">
            <template #header><strong>Current State</strong></template>
            <el-descriptions v-if="conversationState" :column="1" border>
              <el-descriptions-item label="active_account_id">{{ conversationState.active_account_id ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="active_opportunity_id">{{ conversationState.active_opportunity_id ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="active_experiment_id">{{ conversationState.active_experiment_id ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="active_draft_id">{{ conversationState.active_draft_id ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="current_target_type">{{ conversationState.current_target_type || '-' }}</el-descriptions-item>
              <el-descriptions-item label="current_target_id">{{ conversationState.current_target_id ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="last_action">{{ conversationState.last_action || '-' }}</el-descriptions-item>
              <el-descriptions-item label="pending_confirmation">{{ conversationState.pending_confirmation ? 'YES' : '-' }}</el-descriptions-item>
              <el-descriptions-item label="conversation_constraints">{{ formatJson(conversationState.conversation_constraints) }}</el-descriptions-item>
            </el-descriptions>
            <el-empty v-else description="暂无 Current State" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { FileJson, MessageSquareText, Search, Send, ShieldAlert } from 'lucide-vue-next'
import PageHeader from '@/components/PageHeader.vue'
import {
  createAgentConversation,
  executeReadonlyAgentChat,
  getAgentConversation,
  getAgentConversationState,
  listAgentConversationMessages,
  previewAgentChat
} from '@/api/agentChat'
import { createAccountProfile, getAccountProfiles, type AccountProfileResponse } from '@/api/account'
import { getDataSourceConfigByAccount, upsertDataSourceConfig } from '@/api/dataSourceConfig'
import { createDataRefreshRun, listDataRefreshRuns } from '@/api/dataRefreshRun'
import { demoAgentRequest, demoAgentResponse } from '@/mock/agentChatDemo'
import type {
  AccountProfileBusinessResult,
  AgentChatRequest,
  AgentChatResponse,
  CommentInsightSummaryItem,
  ConversationCurrentState,
  ConversationMessageResponse,
  ConversationResponse,
  EntryTraceEvent,
  ValidationIssue
} from '@/types/agentChat'
import type { DataSourceConfigResponse } from '@/types/dataSourceConfig'
import type { DataRefreshRunResponse, RefreshRunStatus } from '@/types/dataRefreshRun'

interface ExampleInput {
  label: string
  text: string
  account_id?: number | null
  experiment_id?: number | null
  current_target_type?: string
  current_target_id?: string
}

const examples: ExampleInput[] = [
  { label: '账号画像', text: '查看当前账号画像' },
  { label: '上下文证据', text: '查看这个账号最近能用于写作的上下文证据' },
  { label: '竞品证据', text: '查看当前账号的竞品证据' },
  { label: '评论洞察', text: '看看评论洞察' },
  { label: '策略记忆', text: '查看策略记忆' },
  { label: '草稿上下文', text: '补充要求：更自然，不要太功利', experiment_id: 1 },
  { label: '新选题', text: '我想写一篇新的小红书选题' },
  { label: '这个不行', text: '这个不行' },
  { label: '标题太 AI', text: '这个标题太 AI 了，换自然一点', current_target_type: 'DRAFT', current_target_id: '123' },
  { label: '自动发布', text: '直接帮我发布到小红书' }
]

const form = reactive({
  session_id: `workbench-${Date.now()}`,
  conversation_id: null as number | null,
  account_id: null as number | null,
  experiment_id: null as number | null,
  text: examples[0].text,
  current_target_type: '',
  current_target_id: ''
})

const response = ref<AgentChatResponse | null>(null)
const loading = ref(false)
const readonlyLoading = ref(false)
const draftContextLoading = ref(false)
const conversationLoading = ref(false)
const errorMessage = ref('')
const demoLoaded = ref(false)
const conversation = ref<ConversationResponse | null>(null)
const conversationMessages = ref<ConversationMessageResponse[]>([])
const conversationState = ref<ConversationCurrentState | null>(null)
const accountLoading = ref(false)
const accounts = ref<AccountProfileResponse[]>([])
const dataSourceLoading = ref(false)
const dataSourceConfig = ref<DataSourceConfigResponse | null>(null)
const refreshLoading = ref(false)
const latestRefreshRun = ref<DataRefreshRunResponse | null>(null)
const refreshRuns = ref<DataRefreshRunResponse[]>([])
const accountSetupForm = reactive({
  account_name: '',
  content_domain: '',
  positioning: '',
  target_audience: ''
})
const dataSourceForm = reactive({
  platform: 'xhs',
  status: 'ACTIVE' as 'ACTIVE' | 'DISABLED',
  keywordsText: '',
  competitorAccountsText: '',
  noteUrlsText: ''
})

const routerIntent = computed(() => response.value?.router_result?.intent || '-')
const planSteps = computed(() => response.value?.plan?.steps || [])
const execution = computed(() => response.value?.metadata.execution || null)
const businessResult = computed(() => response.value?.metadata.business_result || null)
const accountProfileResult = computed(() => {
  const result = businessResult.value
  if (!result) return null
  if (result.account_profile) return result.account_profile
  if (typeof result.account_id === 'number') return result as AccountProfileBusinessResult
  return null
})
const competitorEvidenceResult = computed(() => businessResult.value?.competitor_evidence || null)
const commentInsightResult = computed(() => businessResult.value?.comment_insight || null)
const strategyMemoryResult = computed(() => businessResult.value?.strategy_memory || null)
const draftContextPreviewResult = computed(() => businessResult.value?.draft_context_preview || null)
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
  if (item.account_id !== undefined) form.account_id = item.account_id
  form.experiment_id = item.experiment_id || null
  form.current_target_type = item.current_target_type || ''
  form.current_target_id = item.current_target_id || ''
  demoLoaded.value = false
}

const buildRequest = (overrides: Partial<AgentChatRequest> = {}): AgentChatRequest => ({
  session_id: form.session_id || `workbench-${Date.now()}`,
  conversation_id: form.conversation_id,
  account_id: form.account_id,
  text: form.text,
  input_type: 'TEXT',
  attachments: [],
  context: form.experiment_id ? { experiment_id: form.experiment_id } : {},
  current_target_type: form.current_target_type || null,
  current_target_id: form.current_target_id || null,
  ...overrides
})

const submitPreview = async () => {
  loading.value = true
  errorMessage.value = ''
  demoLoaded.value = false
  try {
    response.value = await previewAgentChat(buildRequest())
    await refreshConversationData()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Agent Chat preview 请求失败'
  } finally {
    loading.value = false
  }
}

const submitReadonlyExecute = async () => {
  readonlyLoading.value = true
  errorMessage.value = ''
  demoLoaded.value = false
  try {
    response.value = await executeReadonlyAgentChat(buildRequest())
    await refreshConversationData()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Agent Chat execute-readonly 请求失败'
  } finally {
    readonlyLoading.value = false
  }
}

const submitDraftContextPreview = async () => {
  draftContextLoading.value = true
  errorMessage.value = ''
  demoLoaded.value = false
  try {
    const context: Record<string, unknown> = {}
    if (form.experiment_id) context.experiment_id = form.experiment_id
    if (form.text.trim()) context.user_requirement = form.text.trim()
    response.value = await executeReadonlyAgentChat(
      buildRequest({
        text: '预览草稿上下文',
        context
      })
    )
    await refreshConversationData()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '草稿上下文预览请求失败'
  } finally {
    draftContextLoading.value = false
  }
}

const createConversation = async () => {
  conversationLoading.value = true
  errorMessage.value = ''
  try {
    conversation.value = await createAgentConversation({
      account_id: form.account_id,
      title: 'Agent 工作台会话'
    })
    form.conversation_id = conversation.value.id
    conversationState.value = conversation.value.current_state
    conversationMessages.value = []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '创建会话失败'
  } finally {
    conversationLoading.value = false
  }
}

const loadConversation = async () => {
  if (!form.conversation_id) {
    errorMessage.value = '请先输入 conversation_id'
    return
  }
  conversationLoading.value = true
  errorMessage.value = ''
  try {
    conversation.value = await getAgentConversation(form.conversation_id)
    conversationState.value = conversation.value.current_state
    conversationMessages.value = await listAgentConversationMessages(form.conversation_id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载会话失败'
  } finally {
    conversationLoading.value = false
  }
}

const refreshConversationData = async () => {
  if (!form.conversation_id) return
  try {
    const [nextConversation, messages, state] = await Promise.all([
      getAgentConversation(form.conversation_id),
      listAgentConversationMessages(form.conversation_id),
      getAgentConversationState(form.conversation_id)
    ])
    conversation.value = nextConversation
    conversationMessages.value = messages
    conversationState.value = state
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '刷新会话失败'
  }
}

const loadAccounts = async () => {
  accountLoading.value = true
  errorMessage.value = ''
  try {
    accounts.value = await getAccountProfiles()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载账号画像失败'
  } finally {
    accountLoading.value = false
  }
}

const createWorkbenchAccount = async () => {
  if (!accountSetupForm.account_name.trim() || !accountSetupForm.positioning.trim() || !accountSetupForm.target_audience.trim()) {
    errorMessage.value = '请先填写账号名称、账号定位和目标用户'
    return
  }
  accountLoading.value = true
  errorMessage.value = ''
  try {
    const account = await createAccountProfile({
      account_name: accountSetupForm.account_name.trim(),
      platform: 'xhs',
      content_domain: accountSetupForm.content_domain.trim() || null,
      positioning: accountSetupForm.positioning.trim(),
      target_audience: accountSetupForm.target_audience.trim(),
      primary_goal: 'lead'
    })
    await loadAccounts()
    form.account_id = account.id
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '创建账号画像失败'
  } finally {
    accountLoading.value = false
  }
}

const loadDataSourceConfig = async () => {
  if (!form.account_id) {
    errorMessage.value = '请先创建或选择账号画像'
    return
  }
  dataSourceLoading.value = true
  errorMessage.value = ''
  try {
    const config = await getDataSourceConfigByAccount(form.account_id, dataSourceForm.platform)
    applyDataSourceConfig(config)
  } catch {
    dataSourceConfig.value = null
    errorMessage.value = '当前账号还没有数据源配置，可以直接保存新配置'
  } finally {
    dataSourceLoading.value = false
  }
}

const saveDataSourceConfig = async () => {
  if (!form.account_id) {
    errorMessage.value = '请先创建或选择账号画像'
    return
  }
  dataSourceLoading.value = true
  errorMessage.value = ''
  try {
    const config = await upsertDataSourceConfig({
      account_id: form.account_id,
      platform: dataSourceForm.platform,
      status: dataSourceForm.status,
      keywords: splitSourceLines(dataSourceForm.keywordsText).map((keyword) => ({ keyword, enabled: true })),
      competitor_accounts: splitSourceLines(dataSourceForm.competitorAccountsText).map((item) =>
        item.startsWith('http')
          ? { profile_url: item, enabled: true }
          : { name: item, enabled: true }
      ),
      note_urls: splitSourceLines(dataSourceForm.noteUrlsText),
      refresh_policy: { manual_only: true },
      metadata_payload: { source: 'agent_workbench_b2' }
    })
    applyDataSourceConfig(config)
    await loadRefreshRuns()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '保存数据源配置失败'
  } finally {
    dataSourceLoading.value = false
  }
}

const runManualRefresh = async () => {
  if (!form.account_id) {
    errorMessage.value = '请先创建或选择账号画像'
    return
  }
  refreshLoading.value = true
  errorMessage.value = ''
  try {
    latestRefreshRun.value = await createDataRefreshRun({
      account_id: form.account_id,
      trigger_type: 'USER_CLICK',
      force: false
    })
    await loadRefreshRuns()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '创建数据刷新运行失败'
  } finally {
    refreshLoading.value = false
  }
}

const loadRefreshRuns = async () => {
  if (!form.account_id) return
  refreshLoading.value = true
  try {
    refreshRuns.value = await listDataRefreshRuns(form.account_id)
    latestRefreshRun.value = refreshRuns.value[0] || latestRefreshRun.value
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '加载刷新记录失败'
  } finally {
    refreshLoading.value = false
  }
}

const applyDataSourceConfig = (config: DataSourceConfigResponse) => {
  dataSourceConfig.value = config
  dataSourceForm.platform = config.platform
  dataSourceForm.status = config.status
  dataSourceForm.keywordsText = config.keywords.map((item) => item.keyword).join('\n')
  dataSourceForm.competitorAccountsText = config.competitor_accounts
    .map((item) => item.name || item.profile_url || item.platform_account_id || '')
    .filter(Boolean)
    .join('\n')
  dataSourceForm.noteUrlsText = config.note_urls.join('\n')
}

const splitSourceLines = (value: string) =>
  Array.from(
    new Set(
      value
        .split(/[\n,，]/)
        .map((item) => item.trim())
        .filter(Boolean)
    )
  )

onMounted(loadAccounts)

const loadLocalDemo = () => {
  Object.assign(form, {
    session_id: demoAgentRequest.session_id || `workbench-${Date.now()}`,
    conversation_id: demoAgentRequest.conversation_id || null,
    account_id: demoAgentRequest.account_id || null,
    experiment_id: Number(demoAgentRequest.context?.experiment_id || '') || null,
    text: demoAgentRequest.text || '',
    current_target_type: demoAgentRequest.current_target_type || '',
    current_target_id: String(demoAgentRequest.current_target_id || '')
  })
  response.value = demoAgentResponse
  conversation.value = null
  conversationMessages.value = []
  conversationState.value = null
  errorMessage.value = ''
  demoLoaded.value = true
}

const statusType = (status?: string) => {
  if (status === 'SUCCESS') return 'success'
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

const summaryList = (items: CommentInsightSummaryItem[]) =>
  items.length ? items.map((item) => `${item.type || item.name || '-'}:${item.count ?? 0}`).join(' / ') : '-'

const messageStatus = (message: ConversationMessageResponse) =>
  typeof message.metadata_payload.status === 'string' ? message.metadata_payload.status : ''

const riskTagType = (riskLevel?: string) => {
  if (riskLevel === 'HIGH' || riskLevel === 'BLOCKED') return 'danger'
  if (riskLevel === 'MEDIUM') return 'warning'
  return 'info'
}

const refreshStatusType = (status: RefreshRunStatus) => {
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILED' || status === 'PROVIDER_NOT_CONFIGURED') return 'warning'
  if (status === 'PARTIAL') return 'warning'
  return 'info'
}

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

.form-grid.single {
  grid-template-columns: minmax(0, 1fr);
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

.conversation-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.data-source-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.data-refresh-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #fde68a;
  border-radius: 8px;
  background: #fffdf4;
}

.refresh-run-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.refresh-run-item {
  padding: 10px;
  border: 1px solid #fef3c7;
  border-radius: 8px;
  background: #ffffff;
}

.account-setup-box {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #bbf7d0;
  border-radius: 8px;
  background: #f7fef9;
}

.compact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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

.business-result,
.result-section,
.mini-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-section {
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message-item {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.message-item p {
  margin: 8px 0;
  color: #374151;
  line-height: 1.6;
}

.message-item span {
  color: #64748b;
  font-size: 12px;
}

.result-summary {
  margin: 0;
  color: #475569;
  line-height: 1.7;
}

.context-slot-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.context-slot-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.slot-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.slot-meta span {
  padding: 3px 6px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #475569;
  font-size: 12px;
}

.slot-preview {
  max-height: 180px;
  margin: 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.mini-card {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.mini-card strong {
  display: block;
  color: #111827;
  font-size: 13px;
}

.mini-card p {
  margin: 6px 0 0;
  color: #475569;
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
