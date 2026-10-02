import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('agent turn HTTP deadline permits the bounded 120 second business LLM policy', async () => {
  const source = await readFile(new URL('../src/api/unifiedAgent.ts', import.meta.url), 'utf8')
  assert.match(source, /sendAgentTurn[\s\S]*timeout:\s*180000/)
})
