import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  ACCOUNT_SELECTION_STORAGE_KEY,
  isMissingOrForbiddenAccountContext,
  persistAccountRef,
  readPersistedAccountRef
} from '../src/stores/accountSelectionPersistence.mjs'

const memoryStorage = (initial = {}) => {
  const values = new Map(Object.entries(initial))
  return {
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
    values
  }
}

test('selected Account 8456 persists and a rebuilt store source can restore it', () => {
  const storage = memoryStorage()
  persistAccountRef(8456, storage)
  assert.equal(storage.getItem(ACCOUNT_SELECTION_STORAGE_KEY), '8456')
  assert.equal(readPersistedAccountRef(storage), 8456)
  assert.equal(readPersistedAccountRef(storage), 8456)

  const storeSource = readFileSync(new URL('../src/stores/agentChat.ts', import.meta.url), 'utf8')
  assert.match(storeSource, /account_ref: readPersistedAccountRef\(\)/)
})

test('switching account replaces the persisted selection', () => {
  const storage = memoryStorage({ [ACCOUNT_SELECTION_STORAGE_KEY]: '8456' })
  persistAccountRef(1, storage)
  assert.equal(readPersistedAccountRef(storage), 1)
})

test('invalid persisted values are cleared without throwing', () => {
  for (const invalid of ['not-a-number', '0', '-1', '1.5', '08456']) {
    const storage = memoryStorage({ [ACCOUNT_SELECTION_STORAGE_KEY]: invalid })
    assert.equal(readPersistedAccountRef(storage), null)
    assert.equal(storage.getItem(ACCOUNT_SELECTION_STORAGE_KEY), null)
  }
})

test('no prior Account selection remains unselected', () => {
  const storage = memoryStorage()
  assert.equal(readPersistedAccountRef(storage), null)
  assert.equal(storage.getItem(ACCOUNT_SELECTION_STORAGE_KEY), null)
})

test('only backend missing or forbidden responses invalidate restored account context', () => {
  assert.equal(isMissingOrForbiddenAccountContext({ response: { status: 403 } }), true)
  assert.equal(isMissingOrForbiddenAccountContext({ response: { status: 404 } }), true)
  assert.equal(isMissingOrForbiddenAccountContext({ response: { status: 500 } }), false)
  assert.equal(isMissingOrForbiddenAccountContext(new Error('network')), false)
})

test('Account persistence does not expand the public Agent request contract', () => {
  const types = readFileSync(new URL('../src/types/unifiedAgent.ts', import.meta.url), 'utf8')
  const request = types.match(/export interface AgentTurnRequest \{[\s\S]*?\n\}/)?.[0] || ''
  assert.doesNotMatch(request, /workflow|tool|checkpoint|planner|intent/)
})
