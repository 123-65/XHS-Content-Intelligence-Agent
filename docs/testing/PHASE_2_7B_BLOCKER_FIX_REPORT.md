# Phase 2.7B 阻塞修复报告

## 一、DEFECT-003 Root Cause

Conversation detail、messages、state 路由只用 `conversation_id` 读取；Service 的 `_get()` 只验证记录存在，没有把当前请求 account identity 与持久化 canonical `conversation.account_id` 比较。消息 cursor 查询同样缺少 ownership gate。

## 二、Security Fix

- 未新增 Route、Migration 或数据库 Schema。
- 正式 Conversation list/detail/messages/state/patch 要求 `account_ref`。
- Service 先加载 canonical Conversation，再比较 `conversation.account_id == account_ref`；不匹配返回 HTTP 403 与 `CONVERSATION_ACCOUNT_MISMATCH`。
- messages pagination 在 ownership guard 之后执行，`before_id` 不能绕过。
- state patch 禁止把 Conversation ownership 转移给其他 Account。
- 前端消息历史请求携带当前 store 的 account_ref。

DEFECT-003：`FIXED / VERIFIED`。

## 三、Account Boundary Regression

- SEC-CONV-001：Account A detail 200；Account B detail 403。
- SEC-CONV-002：Account B messages 403。
- SEC-CONV-003：Account B + before_id 仍为 403。
- SEC-CONV-004：Account A keyset cursor pagination 正常、无重叠。
- 真实 conversation 874 对 Account 8602 的 detail/messages cursor 均为 403。
- Conversation / Unified Agent / Product Read 定向回归：36 passed。
- Research、Strategy、Draft、Publication、Run 既有边界在完整回归中未回归。

## 四、LLM 403 Root Cause

- Unified Client：项目唯一 `LLMClient`。
- Provider / Model：`qwen / qwen-plus`，Mock=false。
- Base URL：账号专属 Model Studio workspace OpenAI-compatible endpoint。
- Secret：仅确认已配置，未输出。
- 配置 health 的 available=true 只表示 key/base URL/model 完整。
- 真实调用返回 HTTP 403，错误类型和 code 均为 `AccessDenied.Unpurchased`。

分类：`MODEL_NOT_PURCHASED`，并表现为 `MODEL_PERMISSION`。不是 WRONG_ENDPOINT、WRONG_MODEL_ID 或 Workflow/Semantic 业务代码问题。

## 五、LLM Smoke Test

通过统一 `LLMClient.generate_structured()` 执行最小真实 smoke：失败，HTTP 403 `AccessDenied.Unpurchased`。没有直接 SDK、没有第二套 Client、没有 Mock、没有输出 Secret。

结论：LLM real smoke test 未通过，禁止恢复 E2E-002。

## 六、E2E-001 Collection Warning Classification

- Profile 1/2：`COLLECTION_ERROR`。Run 保留 partial collection，但未持久化失败 Profile 的细粒度 provider code，不能推断为源数据不存在。
- Comments=0：`PROVIDER_LIMITATION`；证据为 `COMMENTS_PARTIAL_AFTER_TIMEOUT`、`PROVIDER_TIMEOUT_RETRIED`、`COMMENTS_PARTIAL_FROM_PROVIDER`。
- OCR：Provider capability 未配置 warning。
- Note 3/3 和 Research artifact 2862 均成功，故保持 `PARTIAL_SUCCESS / ACCEPTABLE WITH WARNING`。

## 七、Regression

- 定向安全/API：36 passed。
- 完整 pytest：572 passed, 3 skipped, 18 warnings。
- compileall：PASS。
- Frontend：7/7 PASS。
- git diff --check：PASS（仅既有 CRLF 提示）。
- Alembic current/head：`c7d8e9f0a1b2`。
- Migration=0；New Route=0。

18 warnings 中新增计数来自安全测试创建 Account 时触发既有 Pydantic Decimal serializer warning，仍归类 TEST_ENVIRONMENT；未新增 warning 类。

## 八、Phase 2.7B 当前状态

Automated Regression PASS；DEFECT-003 FIXED / VERIFIED；E2E-001 保持真实 PARTIAL_SUCCESS。Phase 2.7B 仍为 `BLOCKED / NOT ACCEPTED`，唯一当前 blocker 为真实 LLM 模型权限。

## 九、下一步

用户需要二选一：

1. 在当前阿里云 Model Studio 账号为 `qwen-plus` 开通/购买调用权限；或
2. 提供项目现有 Adapter 已支持且账号实际可调用的真实低成本模型配置（Qwen、DeepSeek 或 Zhipu 的 provider/base URL/model/key）。

配置完成后先重跑统一 LLMClient structured smoke。只有 smoke PASS、available=true、Mock=false，才使用既有 conversation 874 与 research artifact 2862 恢复 E2E-002；不重跑 E2E-001，不重新采集 URL。
