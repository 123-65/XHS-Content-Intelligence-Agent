# B8 Draft Generation V0

## 目标

B8 让用户在 B7 DraftContextPreview 已经通过后，手动确认生成一篇本地小红书草稿。

本阶段只做草稿生成入口和受控编排，不做发布、不做评论、不访问外部链接、不刷新证据、不重新生成竞品报告，也不创建新的 ContentOpportunity 或 ContentExperiment。

## 复用链路

B8 复用已有 `ContentDraftV2Service` 作为真正的草稿生成链路：

- 继续通过统一 `LLMClient` 调用模型；
- 继续使用已有 prompt / context slot / ContextSnapshot；
- 继续写入已有 `ContentDraft`、`DraftGenerationContext`、`ContentDraftVersion` 和 `PromptRunLog`；
- API 层不直接导入 OpenAI / Qwen / DeepSeek SDK。

B8 新增 `DraftGenerationService` 作为 Agent 产品入口桥接层，负责确认、状态闸门、B7 上下文检查和错误状态映射。

## 接口

```text
POST /agent/content-experiments/{experiment_id}/drafts/generate
```

请求：

```json
{
  "account_id": 1,
  "confirmed": true,
  "user_requirements": "更自然，不要太功利",
  "draft_type": "xhs_note",
  "tone": "natural",
  "model_profile": "default"
}
```

响应状态：

- `WAITING_CONFIRMATION`：用户未确认，不调用 LLM，不创建草稿；
- `CREATED`：草稿已创建；
- `DATA_INSUFFICIENT`：B7 上下文缺必要数据；
- `PROVIDER_NOT_CONFIGURED`：真实 provider 未配置，不伪造成功；
- `BLOCKED`：实验状态不是 READY，或上下文未通过；
- `FAILED`：LLM 输出解析失败、风险校验失败或其他生成失败。

## 闸门规则

1. `confirmed != true` 时直接返回 `WAITING_CONFIRMATION`。
2. 实验不存在返回 404。
3. `account_id` 不匹配返回 400。
4. `experiment.status != READY` 时返回 `BLOCKED`。
5. B7 `ready_for_draft_generation != true` 时不调用 LLM。
6. Provider 未配置时返回 `PROVIDER_NOT_CONFIGURED`，不回退 mock，不生成假草稿。
7. LLM 输出结构化解析失败时返回 `FAILED`，不创建空草稿或假草稿。

## 前端入口

AgentWorkbench 在 B7 草稿上下文预览区下方新增“草稿生成确认”区域：

- 只有 B7 preview ready 后按钮才可用；
- 点击“确认生成本地草稿”会带 `confirmed=true`；
- 页面展示 `draft_id`、provider、preview status、title、content、tags、cta；
- 页面明确提示不会发布到小红书、不会自动评论、不会访问外部链接。

## 边界

B8 不做：

- 真实爬虫；
- 外部链接访问；
- 自动发布；
- 自动评论；
- Evidence 重新生成；
- `CompetitorReportService.create_report`；
- 新建 ContentOpportunity；
- 新建 ContentExperiment；
- LangChain / LangGraph / Mem0 / Langfuse 接入。

## 测试

新增 `backend/tests/test_draft_generation_api.py` 覆盖：

- 未确认不调用 LLM、不创建草稿；
- 实验不存在；
- account mismatch；
- 实验非 READY 阻塞；
- B7 preview 未 ready 阻塞；
- provider 未配置不伪造成功；
- FakeLLMClient 成功生成草稿；
- 成功返回 `draft_id` 和草稿字段；
- LLM 输出无效时失败且不创建草稿；
- 不调用刷新、报告和实验创建工作流；
- 不自动发布。

## 下一步 B9 建议

B9 建议进入 Draft Review / Risk Check V0：

- 对生成后的草稿做结构化审核；
- 输出风险点、修改建议和是否可进入人工发布准备；
- 仍然不自动发布、不自动评论；
- 继续把评论、竞品笔记和截图当作 untrusted input。
