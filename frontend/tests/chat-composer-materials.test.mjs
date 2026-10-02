import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const chat = readFileSync(new URL('../src/views/AgentChatView.vue', import.meta.url), 'utf8')
const store = readFileSync(new URL('../src/stores/agentChat.ts', import.meta.url), 'utf8')

test('composer uses Enter to send while preserving Shift+Enter and IME composition', () => {
  assert.match(chat, /@keydown="handleComposerKeydown"/)
  assert.match(chat, /event\.key !== 'Enter' \|\| event\.shiftKey \|\| event\.isComposing/)
  assert.match(chat, /event\.preventDefault\(\)/)
  assert.match(chat, /if \(canSend\.value\) void send\(\)/)
  assert.match(chat, /Enter 发送 · Shift \+ Enter 换行/)
})

test('material inputs normalize, validate and submit typed URL collections', () => {
  assert.match(chat, /split\(\/\[\\s,，\]\+\//)
  assert.match(chat, /noteUrls\.value\.length > 20 \|\| profileUrls\.value\.length > 20/)
  assert.match(chat, /isXhsNoteUrl/)
  assert.match(chat, /\/user\/profile\//)
  assert.match(chat, /note_urls: noteUrls\.value, profile_urls: profileUrls\.value/)
  assert.match(store, /materials,/)
})

test('successful send clears material fields but failed send retains them', () => {
  const dispatch = chat.indexOf('await store.sendNewTurn')
  const clear = chat.indexOf('clearMaterials()', dispatch)
  const failure = chat.indexOf('} catch (error)', dispatch)
  assert.ok(dispatch >= 0 && clear > dispatch && clear < failure)
  assert.match(chat, /发送时将附带 \{\{ noteUrls\.length \}\} 个笔记链接/)
})
