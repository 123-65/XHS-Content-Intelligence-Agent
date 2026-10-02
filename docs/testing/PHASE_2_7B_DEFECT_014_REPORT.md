# DEFECT-014 Mixed-Goal Contract

## Root Cause

Turn 124 的合法 Pydantic 输出为 `RESEARCH + QUERY_PROFILE`。Profile URL 本应只是 Research input/context，但模型把它额外分类为独立 Control sub-goal。V1 没有定义 mixed Workflow/non-Workflow goal，Semantic 层也没有 post-parse business validation，因此非法组合直到 Planner 才以“多目标包含非 Workflow Intent”失败。

## Frozen Contract

当 primary intent 属于五个 Workflow Intent 时，`sub_goals` 只允许 Workflow Intent。不同类型的独立目标不得静默删除；Semantic post-parse validation 必须拒绝并复用 structured retry。重复 primary/sub-goal 做确定性去重。Planner 原 fail-closed 检查继续作为 defensive safety net。

## Implementation

- Semantic structured/Pydantic PASS 后执行 mixed-goal business validation。
- 非法组合记录 `POST_PARSE_BUSINESS_VALIDATION`，然后进行下一次现有 Semantic attempt。
- retry exhausted 返回现有 `UNKNOWN / NEED_USER_INPUT` 路径，并提示用户拆分独立请求，不暴露内部枚举。
- `LLMClient.record_business_validation_failure()` 支持准确的 attempt number/total/retry exhausted evidence。
- Planner 保留 mixed-goal 防线，并在 UNKNOWN 时传递安全的 Semantic clarification message。

## Verification

- 定向：81 passed。
- Full regression：backend 629 passed / 3 skipped / 18 warnings；frontend 7 passed；typecheck/build/diff/Alembic PASS。
- Migration=0；New Route=0。
- E2E Turn 128 首轮 Semantic 输出再次包含 `QUERY_PROFILE`：OBS 2104 SUCCESS，随后 OBS 2105 `POST_PARSE_BUSINESS_VALIDATION / retryable=true`；第二轮 OBS 2106 SUCCESS，得到合法 RESEARCH Frame，Planner READY，并创建 `RESEARCH_V1` Run `wfr_801e92daac554ed9920927377da55997`。

## Final

`DEFECT-014 = FIXED / REGRESSION VERIFIED / REAL PATH VERIFIED / FROZEN`。

E2E-005 随后在 Workflow `collection_accounts` 因 `XSEC_TOKEN_REQUIRED` 失败，属于新的 XHS Provider 环境阻塞，不是 DEFECT-014 或 DEFECT-013。
