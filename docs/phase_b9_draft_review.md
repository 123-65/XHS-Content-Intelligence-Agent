# B9 Draft Review / Risk Check V0

## 1. B9 目标

B9 让用户在 B8 生成本地 ContentDraftV2 后，手动点击“审核草稿”，系统对草稿做受控风险审核并保存 ReviewReport。

审核输出包括风险等级、综合分、是否建议进入发布准备、问题列表、修改建议、阻塞原因和摘要。

## 2. B9 和 B8 的关系

B8 负责生成本地草稿，B9 只读取 B8 生成的 `ContentDraft` 和关联的 `ContentExperiment`、`AccountProfile`、`generation_context`。

B9 不重新生成草稿，也不重新跑 B7 上下文预览。

## 3. 为什么 B9 不自动修改草稿

审核和改写是两个不同动作。B9 的职责是指出风险和建议，让用户决定是否进入后续修改或发布准备。

本阶段不会写回 draft title/body/tags/cta，也不会更新草稿版本。

## 4. 为什么 B9 不发布

发布属于更高风险动作，需要平台权限、人工最终确认和合规边界。本阶段只判断是否可以进入发布准备，不实现发布。

## 5. ReviewReport 复用情况

项目已有 `ReviewReport` 表、model、schema、repo、service 和旧 API。

B9 复用已有 `ReviewReport` 表，不新增 ReviewReport 表，不新增 migration。旧 `ReviewReportService` 会在审核后修改草稿状态，因此 B9 新增 `DraftReviewService` 作为受控桥接，只创建 ReviewReport，不修改草稿。

## 6. LLM 调用边界

B9 可以调用模型做审核，但只能通过统一 `LLMClient`。

API 层不直接 import Qwen / DeepSeek / OpenAI SDK。Provider 未配置时返回 `PROVIDER_NOT_CONFIGURED`，不 fallback 到 mock，不伪造 ReviewReport。测试使用 FakeLLMClient。

## 7. 审核维度

B9 审核维度包括：

- 安全与合规风险；
- AI 味和可读性；
- 夸大承诺、焦虑营销、过强 CTA；
- 与证据链、ContentExperiment、AccountProfile 的一致性；
- 是否可以进入发布准备。

## 8. Provider 未配置处理

当 `LLMClient` 抛出 `LLM_CONFIG_MISSING` 或 `LLM_PROVIDER_UNAVAILABLE` 时，B9 返回 `PROVIDER_NOT_CONFIGURED`。

此时不创建 ReviewReport，不创建假审核结果。

## 9. 数据不足 / 草稿不存在处理

草稿不存在返回 404。账号不匹配返回 400。未确认时返回 `WAITING_CONFIRMATION`，不调用 LLM，不创建 ReviewReport。

## 10. 前端展示内容

AgentWorkbench 在 B8 草稿生成结果后展示 Draft Review V0：

- 当前 `draft_id`；
- 审核按钮；
- `review_report_id`；
- `risk_level`；
- `score`；
- `can_enter_publish_preparation`；
- issues；
- suggestions；
- provider 未配置提示。

页面明确提示：本步骤可能调用模型并消耗额度，只审核草稿，不会修改草稿，不会发布到小红书，不会自动评论。

## 11. 测试结果

新增 `backend/tests/test_draft_review_api.py`，覆盖确认门、草稿不存在、账号不匹配、Provider 未配置、FakeLLMClient 成功审核、高风险阻塞、LLM 失败不落库、不调用上游工作流、不改草稿、不发布。

完整测试结果以提交前终端输出为准。

## 12. 本阶段没有做什么

B9 没有修改草稿，没有自动发布，没有自动评论，没有重新生成草稿，没有重新生成 Evidence，没有重新调用 `CompetitorReportService.create_report`，没有引入 LangChain / LangGraph / Mem0 / Langfuse。

## 13. 下一步 B10 计划

B10 建议进入 Draft Feedback / Revision Planning V0：

- 用户基于 B9 审核结果选择要修改的方向；
- 生成受控修改计划；
- 人工确认后再进入草稿改写；
- 继续禁止自动发布和自动评论。
