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
  if (message.id && pending.has(message.id)) {
    pending.get(message.id)(message)
    pending.delete(message.id)
  }
  if (message.method === 'Network.loadingFailed' && !message.params.canceled) failures.push(message.params.errorText)
  if (message.method === 'Network.responseReceived' && message.params.response.status >= 400) {
    failures.push(`${message.params.response.status} ${message.params.response.url}`)
  }
  if (message.method === 'Runtime.exceptionThrown') consoleErrors.push(message.params.exceptionDetails.text)
  if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') {
    consoleErrors.push(message.params.args.map(arg => arg.value || arg.description).join(' '))
  }
}
const call = (method, params = {}) => new Promise((resolve, reject) => {
  const callId = ++id
  pending.set(callId, message => message.error ? reject(new Error(message.error.message)) : resolve(message.result))
  ws.send(JSON.stringify({ id: callId, method, params }))
})
const evaluate = async expression => (await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result.value
const waitFor = async (expression, label, timeout = 12000) => {
  const started = Date.now()
  while (Date.now() - started < timeout) {
    if (await evaluate(expression)) return
    await new Promise(resolve => setTimeout(resolve, 150))
  }
  throw new Error(`Timed out: ${label}`)
}
const clickContaining = async (selector, text) => {
  const clicked = await evaluate(`(()=>{const el=[...document.querySelectorAll(${JSON.stringify(selector)})].find(x=>x.textContent.includes(${JSON.stringify(text)})&&x.getBoundingClientRect().width>0);if(!el)return false;el.click();return true})()`)
  if (!clicked) throw new Error(`Missing clickable: ${text}`)
}
const expectText = async (texts, label) => {
  for (const text of texts) await waitFor(`document.body.textContent.includes(${JSON.stringify(text)})`, `${label}: ${text}`)
}

await call('Page.enable')
await call('Runtime.enable')
await call('Network.enable')
await waitFor("document.readyState==='complete'", 'initial page')
await evaluate("localStorage.setItem('xhs-growth:selected-account-ref','8456')")
await call('Page.navigate', { url: `${base}/agent/chat?usability=v1` })
await waitFor("location.pathname==='/agent/chat' && localStorage.getItem('xhs-growth:selected-account-ref')==='8456' && document.querySelectorAll('.el-menu-item').length>=7", 'Account 8456 restore and navigation')

await clickContaining('.el-menu-item', 'Research')
await waitFor("location.pathname==='/agent/research' && document.querySelector('.asset-row')", 'Research list')
await clickContaining('.asset-row', '')
await waitFor("location.pathname.startsWith('/agent/research/')", 'Research detail')
await expectText(['研究结论', '数据来源', '缺失数据与限制', '选择到对话'], 'Research UX')

await clickContaining('.el-menu-item', 'Strategy')
await waitFor("location.pathname==='/agent/strategy' && document.querySelector('.asset-row')", 'Strategy list')
await expectText(['来自研究', '目标受众'], 'Strategy list UX')
await clickContaining('.asset-row', '')
await waitFor("location.pathname.startsWith('/agent/strategy/')", 'Strategy detail')
await expectText(['内容策略', '来自 Research', '下一步'], 'Strategy UX')

await clickContaining('.el-menu-item', 'Draft')
await waitFor("location.pathname==='/agent/draft' && document.body.textContent.includes('2625')", 'Draft list')
await expectText(['最新 V5', '已发布 V2', '进入详情', '选择到对话'], 'Draft list UX')
await clickContaining('.draft-main', '2625')
await waitFor("location.pathname==='/agent/draft/2625'", 'Draft 2625 detail')
await expectText(['最新版本', 'V5', '实际发布版本', 'V2', '选择要查看或发布的版本', '生成 V5 发布包'], 'Draft detail UX')

await clickContaining('.el-menu-item', 'Published Content')
await waitFor("location.pathname==='/agent/publications' && document.querySelector('.asset-row')", 'Publication list')
await expectText(['实际发布 V2', '查看实际发布版本、表现数据与复盘结果'], 'Publication list UX')
await clickContaining('.asset-row', '')
await waitFor("location.pathname==='/agent/publication/592'", 'PublishedNote 592 detail')
await expectText([
  '实际发布版本', 'V2', '当前最新草稿版本', 'V5', '公开表现数据', '暂无数据',
  '用户填写的转化数据', '私信咨询数', '3', '微信新增数', '1', '未填写',
  '录入 / 更新数据', '开始复盘', '复盘结论', '下一轮策略建议'
], 'Publication and Review UX')
await clickContaining('button', '录入 / 更新数据')
await expectText(['统计时间范围', '未填写和 0 含义不同', '保存转化数据'], 'Private metrics form')

await clickContaining('.el-menu-item', 'Review')
await waitFor("location.pathname==='/agent/reviews' && document.body.textContent.includes('复盘记录 2144')", 'Review 2144 list')
await expectText(['发布后复盘', '绑定已发布内容 592'], 'Review list UX')
await clickContaining('.asset-row', '2144')
await waitFor("location.pathname==='/agent/publication/592'", 'Review detail mapping')
await expectText(['绑定的已发布内容', '592', '复盘结论', '下一轮策略建议'], 'Review lineage')

await clickContaining('button', '开始复盘')
await waitFor("location.pathname==='/agent/chat'", 'Review to Agent Chat')
await expectText(['当前工作对象', '已发布内容', '实际发布 V2', '查看详情', '清除选择'], 'Current Context Card')

console.log(JSON.stringify({
  account_ref: 8456,
  research: true,
  strategy: true,
  draft_2625: { latest_version: 5, published_version: 2 },
  published_note_592: { exact_version: 2, private_metrics: { dm_count: 3, wechat_add_count: 1 } },
  review_2144: { published_note_ref: 592 },
  private_metrics_form_opened_without_submit: true,
  current_context_card: true,
  failures,
  consoleErrors
}))
ws.close()
if (failures.length || consoleErrors.length) process.exitCode = 1
