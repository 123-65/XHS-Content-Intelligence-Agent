import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const root = new URL('../src/', import.meta.url)
const read = (path) => readFileSync(new URL(path, root), 'utf8')
const router = read('router/index.ts')
const layout = read('components/AppLayout.vue')
const api = read('api/unifiedAgent.ts')

const lists = [
  ['Research', 'agentResearchList', 'agentResearch'],
  ['Strategy', 'agentStrategyList', 'agentStrategy'],
  ['Draft', 'agentDraftList', 'agentDraft'],
  ['Publication', 'agentPublicationList', 'agentPublication'],
  ['Review', 'agentReviewList', 'agentPublication']
]

test('all core asset lists are lazy routes and discoverable through named router links', () => {
  for (const [view, listRoute] of lists) {
    assert.match(router, new RegExp(`name: '${listRoute}', component: \\(\\) => import\\([^\\n]+${view}ListView\\.vue`))
    assert.match(layout, new RegExp(`router\\.resolve\\(\\{ name: '${listRoute}' \\}\\)\\.path`))
  }
  for (const label of ['Agent 对话', 'Research', 'Strategy', 'Draft', 'Published Content', 'Review', 'Trace 控制台']) {
    assert.match(layout, new RegExp(label))
  }
})

test('asset list API contract always carries account scope and bounded pagination', () => {
  assert.match(api, /account_ref: accountRef, page_no: pageNo, page_size: pageSize/)
  for (const method of ['getResearchList', 'getStrategyList', 'getDraftList', 'getPublicationList', 'getReviewList']) {
    assert.match(api, new RegExp(`export const ${method}`))
  }
  assert.doesNotMatch(api, /workflow_id|tool_name|checkpoint/)
})

test('each list links to an existing canonical detail route and never infers account identity', () => {
  for (const [view, , detailRoute] of lists) {
    const source = read(`views/agent/${view}ListView.vue`)
    assert.match(source, /store\.account_ref/)
    assert.match(source, new RegExp(`name: '${detailRoute}'`))
    assert.doesNotMatch(source, /8456|localStorage|artifact.*account/i)
  }
})
