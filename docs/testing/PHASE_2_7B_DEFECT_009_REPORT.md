# Phase 2.7B DEFECT-009 Evidence Report

## 一、Expected

Turn 84 使用可信 Workspace Selection `opportunity_ref=3956` 与自然语言“用这个写一篇，语气自然一点。”。Semantic 应识别 CONTENT_CREATE，Resolver 应把“这个”确定性绑定到 Workspace Opportunity 3956，Planner 随后启动 `CONTENT_CREATION_V1`。

## 二、Actual

- Conversation：874
- AgentTurn：84
- Client Request：`phase27b-e2e003-defect008-retry-20260923-01`
- HTTP：200
- Latency：14,321 ms
- Intent：`CONTENT_CREATE`
- Action / Status：`CLARIFY / WAITING_USER`
- Reason：`这个: REFERENCE_CONTEXT_MISSING`
- Run Ref：无

## 三、Failure Stage

DEFECT-008 的 Workspace ownership lookup 已成功。真实 Control Semantic 首轮 SUCCESS 后，Context Resolver 未能用 workspace 中唯一可信的 generated Opportunity 3956 消解“这个”，Planner 因 blocking missing info 返回 CLARIFY。

## 四、Evidence

- Structured semantic evidence：`control_agent_semantic_layer / SUCCESS / attempt 1 / is_mock=false`。
- Semantic intent 为 CONTENT_CREATE，constraints 数组非空；自然语气要求已进入 structured output。
- Workspace request 只包含 `opportunity_ref=3956`，没有完整业务 JSON。
- Turn result 明确记录 `REFERENCE_CONTEXT_MISSING`。

## 五、Partial Data

- Turn 84 与 user/assistant message 已正式保存。
- CONTENT_CREATION_V1 Run：0
- Draft Root / Version：0
- Operation Ledger：0
- Draft/Review LLM call：0
- Research / Strategy / XHS collection：0

## 六、Status

RCA 确认：Turn 84 的双重脱敏哈希可确定 `SemanticReference.type=UNKNOWN`、`raw_text=这个`。Workspace Opportunity 3956 已进入 Resolver input，但旧 `_resolve_one()` 在 `TYPE_MAP` 找不到 UNKNOWN 后直接产生 `REFERENCE_CONTEXT_MISSING`，尚未枚举 Workspace candidate。CONTENT_CREATE typed input 明确要求 Opportunity。

最小修复仅位于 Context Resolver：对 `UNKNOWN + 有限 deictic expression + Intent expected type` 走原有 priority 与 canonical identity validation。V1 仅支持“这个”“这个选题”“刚才选的这个”“它”；不是 contains 匹配，也不把所有 UNKNOWN 映射为 Opportunity。CONTENT_STRATEGY→Research、CONTENT_CREATE→Opportunity、CONTENT_REFINE→Draft、POST_PUBLISH_REVIEW→Published Note。多候选仍 ambiguous，错误类型不替代，跨 Account 仍拒绝，explicit/ordinal 既有优先语义不变。

定向回归 82 passed；完整 backend 598 passed / 3 skipped / 18 warnings；frontend 7/7、typecheck、production build、Alembic current/head 与 diff check 均 PASS。

真实 Turn 91 使用新的 client request，成功得到 `CONTENT_CREATE / EXECUTE_PLAN` 并创建 `CONTENT_CREATION_V1` Run `wfr_02c20c262f3c40a68e1fc94705b1741b`。Run input 为 Strategy 13 / Opportunity 3956，state lineage 为 Research 2862 / source 3923；证明 deictic Context 与 Planner 路径已真实通过。

`DEFECT-009 = FIXED / VERIFIED`

随后 Evidence Retrieval 出现新的 `DEFECT-010`：`Opportunity Evidence 类型不可检索: content_opportunity`。因此 `E2E-003 = FAILED / BLOCKED BY DEFECT-010`。

按 Stop Point 未继续修复、未执行 E2E-004 或 Testing Track。
