const base = 'http://localhost:5173'
const endpoint = process.env.CDP_ENDPOINT || 'http://127.0.0.1:9333'
const target = await fetch(`${endpoint}/json/new?${encodeURIComponent(`${base}/agent/chat`)}`, { method: 'PUT' }).then(r => r.json())
const ws = new WebSocket(target.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject })
let id = 0
const pending = new Map()
const failures = []
const consoleErrors = []
ws.onmessage = ({ data }) => {
  const message = JSON.parse(data)
  if (message.id && pending.has(message.id)) { pending.get(message.id)(message); pending.delete(message.id) }
  if (message.method === 'Network.loadingFailed') failures.push(message.params.errorText)
  if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) failures.push(`${message.params.response.status} ${message.params.response.url}`)
  if (message.method === 'Runtime.exceptionThrown') consoleErrors.push(message.params.exceptionDetails.text)
  if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') consoleErrors.push(message.params.args.map(arg => arg.value || arg.description).join(' '))
}
const call = (method, params = {}) => new Promise((resolve, reject) => {
  const callId = ++id; pending.set(callId, message => message.error ? reject(new Error(message.error.message)) : resolve(message.result)); ws.send(JSON.stringify({ id: callId, method, params }))
})
const evaluate = async expression => (await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value
const waitFor = async (expression, label, timeout = 10000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) { if (await evaluate(expression)) return; await new Promise(r => setTimeout(r, 150)) }
  throw new Error(`Timed out: ${label}`)
}
const clickText = async (selector, text) => {
  const point = await evaluate(`(()=>{const el=[...document.querySelectorAll(${JSON.stringify(selector)})].find(x=>x.textContent.trim()===${JSON.stringify(text)}&&x.getBoundingClientRect().width>0);if(!el)return null;const r=el.getBoundingClientRect();return{x:r.left+r.width/2,y:r.top+r.height/2}})()`)
  if (!point) throw new Error(`Missing clickable ${text}`)
  await call('Input.dispatchMouseEvent', { type: 'mousePressed', x: point.x, y: point.y, button: 'left', clickCount: 1 })
  await call('Input.dispatchMouseEvent', { type: 'mouseReleased', x: point.x, y: point.y, button: 'left', clickCount: 1 })
}

await call('Page.enable'); await call('Runtime.enable'); await call('Network.enable')
await waitFor("document.readyState==='complete' && document.querySelector('.el-select')", 'Agent Chat')
await evaluate("localStorage.setItem('xhs-growth:selected-account-ref','8456')")
await call('Page.navigate', { url: `${base}/agent/chat?browser_acceptance=026` })
await waitFor("location.search.includes('browser_acceptance=026') && document.readyState==='complete' && document.querySelector('.el-select') && localStorage.getItem('xhs-growth:selected-account-ref')==='8456'", 'Account 8456 restore')

await clickText('.el-menu-item', 'Draft')
await waitFor("location.pathname==='/agent/draft' && document.body.textContent.includes('2625')", 'Draft 2625 list')
const draftOpened = await evaluate("(()=>{const row=[...document.querySelectorAll('.asset-row')].find(x=>x.textContent.includes('2625'));if(!row)return false;row.click();return true})()")
if (!draftOpened) throw new Error('Draft 2625 row missing')
await waitFor("location.pathname==='/agent/draft/2625'", 'Draft detail route')
if (await evaluate("document.body.textContent.includes('请先选择账号')")) throw new Error('Draft detail lost Account context')

for (const [label, path, heading] of [
  ['Research', '/agent/research', 'Research'], ['Strategy', '/agent/strategy', 'Strategy'],
  ['Published Content', '/agent/publications', '592'], ['Review', '/agent/reviews', '2144']
]) {
  await clickText('.el-menu-item', label)
  await waitFor(`location.pathname===${JSON.stringify(path)} && document.body.textContent.includes(${JSON.stringify(heading)})`, label)
}

console.log(JSON.stringify({ account_ref: 8456, draft_list: true, draft_2625_detail: true, research: true, strategy: true, publications: true, reviews: true, failures, consoleErrors }))
ws.close()
if (failures.length || consoleErrors.length) process.exitCode = 1
