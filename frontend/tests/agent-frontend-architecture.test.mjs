import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = new URL('../src/', import.meta.url)
const read = (path) => readFileSync(new URL(path, root), 'utf8')
const router = read('router/index.ts')
const chat = read('views/AgentChatView.vue')
const store = read('stores/agentChat.ts')
const api = read('api/unifiedAgent.ts')

test('Agent Chat and every detail view are route-lazy chunks', () => {
  for (const view of ['AgentChatView', 'ResearchDetailView', 'StrategyDetailView', 'DraftDetailView', 'PublicationDetailView', 'RunDetailView']) {
    assert.match(router, new RegExp(`component: \\(\\) => import\\([^\\n]+${view}\\.vue`))
  }
  assert.doesNotMatch(chat, /ResearchDetailView|StrategyDetailView|DraftDetailView|PublicationDetailView/)
})

test('production natural-language entry is only the unified turn endpoint', () => {
  assert.match(api, /post<unknown, AgentTurnResponse>\('\/api\/agent\/turns'/)
  const apiDir = new URL('api/', root)
  const apiPath = fileURLToPath(apiDir)
  const productionApis = readdirSync(apiPath).filter(name => name.endsWith('.ts')).map(name => readFileSync(join(apiPath, name), 'utf8')).join('\n')
  assert.doesNotMatch(productionApis, /execute-workflow|workflow\/resume|Runtime\.resume/)
})

test('chat does not fetch artifact detail and stores ref-only workspace selection', () => {
  assert.doesNotMatch(chat, /getResearch|getStrategy|getDraft|getPublication|artifactDetail/)
  assert.match(store, /workspace_selection: \{\} as WorkspaceSelection/)
  assert.doesNotMatch(store, /evidence_history|draft_versions|metrics_history|artifact_json/)
})

test('pending, partial warning, failure and success artifact summaries have explicit render paths', () => {
  assert.match(chat, /store\.pending_interaction/)
  assert.match(chat, /message\.warnings/)
  assert.match(chat, /active_status === 'FAILED'/)
  assert.match(chat, /message\.artifacts/)
})

test('retry reuses request while account switch clears scoped state', () => {
  assert.match(store, /return this\.dispatch\(this\.retry_state\)/)
  assert.match(store, /client_request_id: uid\(\)/)
  for (const reset of ['conversation_id = null', 'workspace_selection = {}', 'pending_interaction = null', 'active_run_ref = null']) {
    assert.match(store, new RegExp(reset.replace(/[{}]/g, '\\$&')))
  }
})

test('detail routes own independent loading boundaries', () => {
  const run = read('views/agent/RunDetailView.vue')
  for (const view of ['ResearchDetailView', 'StrategyDetailView', 'DraftDetailView', 'PublicationDetailView']) {
    const source = read(`views/agent/${view}.vue`)
    assert.match(source, /onBeforeUnmount\(\(\)=>controller\.abort\(\)\)/)
    assert.match(source, /controller\.signal/)
  }
  assert.match(run, /getAgentRun/)
  assert.match(run, /controller\.signal/)
})

test('conversation uses server cursor and production gap placeholder is gone', () => {
  assert.match(store, /history_next_cursor/)
  assert.match(store, /loadEarlierMessages/)
  assert.match(api, /before_id/)
  const detailSources = ['ResearchDetailView', 'StrategyDetailView', 'DraftDetailView', 'PublicationDetailView']
    .map(view => read(`views/agent/${view}.vue`)).join('\n')
  assert.doesNotMatch(detailSources, /ARTIFACT_DETAIL_READ_API_GAP/)
  assert.match(detailSources, /getResearchDetail/)
  assert.match(detailSources, /getPublicationDetail/)
})
