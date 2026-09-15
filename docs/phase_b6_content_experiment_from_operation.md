# Phase B6 Content Experiment Creation / 从运营推荐创建内容实验 V0

## 1. B6 目标

B6 让用户从 B5 今日运营分析的 recommendations 中选择一条推荐方向，经人工确认后创建本地 ContentExperiment。

本阶段只完成“运营推荐 -> 本地内容实验”的桥接，不生成草稿，不发布到小红书，不调用 LLM。

## 2. 为什么 B6 是内容实验，不是草稿生成

B5 的 recommendation 只说明今天优先关注什么方向。B6 进一步把这个方向变成可跟踪的内容实验，用于后续验证选题、角度和指标。

草稿生成需要更完整的写作上下文、用户确认和生成链路，因此不放在 B6。

## 3. B5 Recommendation 到 ContentExperiment 的映射

B6 读取 OperationRun.recommendations 中指定 rank 的推荐项，并用其中的 `opportunity_id` 查询 B4 已生成的 ContentOpportunity。

映射方式：

- `experiment_name`：用户传入值，否则使用 recommendation.title / opportunity.opportunity_title；
- `analysis_report_id`：OperationRun.report_id；
- `content_opportunity_id`：ContentOpportunity.id；
- `selected_topic`：ContentOpportunity.opportunity_title；
- `topic_angle`：ContentOpportunity.suggested_angle；
- `hypothesis`：基于 opportunity title、angle 和 target_metric 形成简单实验假设；
- `target_metric`：用户传入值，默认 collect；
- `expected_result` / `target_values`：按目标指标生成本地实验目标；
- `source_type`：`OPERATION_RUN_RECOMMENDATION`。

内容理解仍然来自 B4 的 ContentOpportunity，B6 不重新分析内容。

## 4. 后端新增内容

新增桥接文件：

- `backend/app/schemas/operation_experiment.py`
- `backend/app/services/operation_experiment_sev.py`
- `backend/app/api/operation_experiment.py`
- `backend/tests/test_operation_experiment_api.py`

小范围修改：

- `backend/app/main.py` 注册新 router；
- `backend/app/schemas/content_experiment.py` 将 `OPERATION_RUN_RECOMMENDATION` 加入已有 source_type 白名单。

没有新增 ContentExperiment 表，也没有新增 migration。

## 5. 前端新增内容

新增：

- `frontend/src/api/operationExperiment.ts`
- `frontend/src/types/operationExperiment.ts`

修改：

- `frontend/src/views/AgentWorkbench.vue`

在 B5 recommendations 下增加“创建内容实验”按钮。点击后先调用 preview 接口展示确认卡，用户点击确认后才调用 create 接口。

## 6. 人工确认机制

B6 是本地写库动作，必须人工确认。

- preview 接口不写库；
- create 接口 `confirmed != true` 时返回 `WAITING_CONFIRMATION`，不写库；
- create 接口 `confirmed=true` 时才创建 ContentExperiment；
- 前端确认卡展示推荐标题、推荐原因、证据摘要、opportunity_id、risk_level、confidence、实验名称和目标指标；
- 确认卡明确提示：只创建本地内容实验，不会发布到小红书，不会生成草稿，不会调用 LLM。

## 7. 数据不足处理

以下情况不会创建实验：

- OperationRun 不存在；
- OperationRun.account_id 与请求 account_id 不一致；
- OperationRun 状态为 DATA_INSUFFICIENT / FAILED；
- recommendation rank 不存在；
- recommendation 没有 opportunity_id；
- opportunity_id 查询不到 ContentOpportunity；
- ContentOpportunity.report_id 与 OperationRun.report_id 不一致。

## 8. 为什么本阶段不调用 LLM

B6 只做结构化字段映射和本地写库，不需要模型理解。调用 LLM 会增加不确定性，也可能绕过 B5/B4 已经沉淀的证据结构。

## 9. 为什么本阶段不生成草稿

实验是“要验证什么”的计划，草稿是“具体怎么写”的产物。B6 只创建实验，后续 B7 再围绕已确认的实验进入草稿上下文和生成链路。

## 10. 为什么本阶段不自动发布

发布是外部平台动作，风险高于本地实验创建。B6 不接小红书发布能力，不访问外部链接，也不做自动评论。

## 11. 测试结果

本阶段测试覆盖：

- preview 不写库；
- confirmed=false 不写库并返回 WAITING_CONFIRMATION；
- confirmed=true 创建 ContentExperiment；
- OperationRun 不存在返回 404；
- account_id 不匹配返回 400；
- OperationRun DATA_INSUFFICIENT 时不能创建；
- recommendation rank 不存在时不能创建；
- recommendation 没有 opportunity_id 时不能创建；
- opportunity_id 不存在时不能创建；
- 创建后返回 experiment_id；
- 不调用 LLM；
- 不访问外部链接；
- 不创建 report；
- 不创建 opportunity；
- 不重新生成 EvidenceRefreshRun；
- 不重新生成 OperationRun。

## 12. 下一步 B7 计划

B7 可以基于已确认的 ContentExperiment 做草稿上下文预览或草稿生成前确认。建议继续保持受控链路：

1. 用户选择一个实验；
2. 系统读取 experiment、opportunity、report 和 evidence；
3. 展示草稿上下文确认卡；
4. 用户确认后才进入草稿生成；
5. 仍然不自动发布、不自动评论。
