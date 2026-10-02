import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../src/', import.meta.url)
const read = path => readFileSync(new URL(path, root), 'utf8')
const chat = read('views/AgentChatView.vue')
const store = read('stores/agentChat.ts')
const research = read('views/agent/ResearchDetailView.vue')
const draftList = read('views/agent/DraftListView.vue')
const draft = read('views/agent/DraftDetailView.vue')
const publication = read('views/agent/PublicationDetailView.vue')
const api = read('api/unifiedAgent.ts')
const presentation = read('utils/presentation.ts')
const types = read('types/unifiedAgent.ts')

test('chat exposes a usable current context and translates pending requirements', () => {
  assert.match(chat, /当前工作对象/)
  assert.match(chat, /查看详情/)
  assert.match(chat, /清除选择/)
  assert.match(chat, /fieldLabels/)
  assert.match(chat, /技术详情/)
  assert.match(store, /workspace_context_display/)
  assert.match(types, /detail_route/)
})

test('business status and metric vocabulary are human readable', () => {
  for (const label of ['需要补充信息', '部分完成', '执行失败', '暂无数据', '用户填写', '已修改']) assert.match(presentation, new RegExp(label))
  for (const label of ['私信咨询数', '微信新增数', '有效咨询数', '成交数', '成交金额']) assert.match(presentation, new RegExp(label))
  assert.match(presentation, /value === null \|\| value === undefined \? '未填写' : String\(value\)/)
})

test('research, draft and publication explain lineage and next actions', () => {
  assert.match(research, /研究结论/)
  assert.match(research, /数据来源/)
  assert.match(research, /缺失数据与限制/)
  assert.match(draftList, /publishedVersion/)
  assert.match(draftList, /选择到对话/)
  assert.match(draft, /实际发布版本/)
  assert.match(publication, /实际发布版本/)
  assert.match(publication, /当前最新草稿版本/)
  assert.match(publication, /开始复盘/)
  assert.match(publication, /下一轮策略建议/)
})

test('private metrics form uses only the canonical existing API', () => {
  assert.match(api, /\/api\/published-notes\/\$\{publishedNoteRef\}\/private-metrics/)
  assert.match(publication, /recordPrivateMetrics/)
  assert.match(publication, /未填写和 0 含义不同/)
  assert.doesNotMatch(api, /start-review|create-review|execute-workflow/)
})
