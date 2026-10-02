# Black-Box Frontend Agent Evaluation v1

## 1. Environment

- 唯一产品入口：`http://127.0.0.1:5173`
- 浏览器：真实 Edge（CDP 仅驱动点击、键盘、DOM 读取和 Console/Network 故障观察）
- Account 合同：8456
- UI 展示名：`E2E 考公考编验收 20260923`
- 数据来源：仅用户可见 UI 与 Trace 控制台
- 未使用 SQL、ORM、Repository、Backend API、Fixture、直接 Workflow/Tool 调用
- 按用户补充要求未保存截图，只保存完整回答与响应信息

## 2. Case Count

- 总计：30
- 实际 UI 执行：30
- D03 已在补充第三个授权 Profile URL 后完成重测

## 3. PASS / FAIL / BLOCKED

- PASS：6（20.00%）
- FAIL：24（80.00%）
- BLOCKED：0
- PASS：A01、B05、C02、C03、C09、G03

## 4. Intent Accuracy

- 20 / 30 = 66.67%
- 明确问题：能力问答 A03/A04/A05 全部退化为同一句欢迎语；自动发布/自动评论没有识别为能力边界；部分 Strategy/Review 请求产生无回复。

## 5. Material Extraction Accuracy

- 0 / 8 = 0%
- Profile URL、Note URL、Pending 后仅补 URL 均未从聊天文本形成材料。
- URL query（含 `xsec_token`）在可见回答中仍完整，问题不是前端截断，而是没有转换为 canonical material。
- D03 完整读取三条 URL，但将三条都解释为 `REFERENCE_CONTEXT_MISSING`，没有形成三个 `XHS_PROFILE_URL` material。

## 6. Context Accuracy

- 6 / 16 = 37.50%
- Draft 2625 的明确 revision 指令可以工作。
- Research、Strategy、PublishedNote 的 Current Context Card 虽正确显示，但 Agent 多次仍返回 `REFERENCE_CONTEXT_MISSING` 或无回复。
- 无 Workspace 的 C09 能进入 Pending，但内部错误码仍作为主要回答暴露。

## 7. Workflow Routing Accuracy

- 用户可见推断：15 / 30 = 50.00%。
- 其中包含“正确不启动 Workflow”的 Conversation/Clarify Case。
- Trace 控制台没有出现可与本批 Turn 关联的新 Run，因此具体 Workflow 名称保持 UNKNOWN，不将其偷偷计为 PASS。

## 8. Tool Selection Accuracy

- 0 / 15 = 0%（其余 UNKNOWN）。
- 需要 Tool 的失败 Case 没有可见执行证据。
- 4 个 revision Case 有真实产物，但 Trace 无新 Run，无法证明准确 Tool 名称，严格记 UNKNOWN。

## 9. Tool Execution Success

- 4 / 19 = 21.05%。
- B05、C02、C03、J01 有可见 Draft 产物。
- Research、Strategy、Draft creation、Review 主链路未形成可见产物。

## 10. Grounding

- 1 / 7 = 14.29%，J01 为 UNKNOWN。
- G03 在无 Research 时要求 `research_artifact_ref`，没有伪装成数据驱动策略，因此 grounding 行为通过，但文案仍是内部字段名。
- E01/E02/E05 均在材料阶段失败，不能评估真实 Research grounding。
- N05 没有进入 Review，无法验证 Published V2、public/private metrics 与 Research context。

## 11. Final Action Success

- 6 / 30 = 20.00%。
- Draft refinement 是唯一稳定形成可见业务产物的执行路径。

## 12. Response Quality

- 人工平均分：1.43 / 5。
- 主要问题：固定欢迎语、内部字段/错误码直出、“任务执行完成”缺少变更摘要、Pending 字段全部被翻译成“必要信息”、请求失败后 UI 可出现只有用户消息而无 AI 解释。

## 13. Fake Success Rate

- 3 / 30 = 10.00%。
- A03/A04/A05 对三个不同能力问题均返回与 A01 相同的固定欢迎语并显示“已完成”。
- Draft revision 返回“已完成”时同时存在可见 Draft 产物，因此未判 Fake Success，但回复质量较低。

## 14. Conversation Findings

- A01 自然问候通过。
- A03/A04/A05 无法回答能力、Skill、Tool，且语义不敏感。
- A07/A08 将明确不支持的能力错误处理为“缺参数”，没有表达自动发布/自动评论边界。

## 15. Research Findings

- 从聊天正文输入授权 Profile/Note URL 时，材料抽取成功率为 0%。
- E01/E02/E05 均未创建 Research Artifact。
- 因 Research 未启动，真实 Provider、Evidence、指标 UNKNOWN 和反事实差异均无法验证。

## 16. Strategy Findings

- 从 UI 选择 Research 后，Current Context Card 显示正确，但 B03/G01 只有用户消息，30 秒后没有 AI 回复或策略产物。
- 无 Research 的 G03 能拒绝凭空生成，但直接暴露 `research_artifact_ref`。

## 17. Draft Findings

- Draft 2625 的明确修改请求 B05/C02/C03 可执行并返回同一 Draft 产物。
- 本轮真实 UI 操作使 Draft 2625 从 V5 演进到 V10；这是评测中的正式用户操作，不是数据库直写。
- J01 创建了可见新版本，但回答没有提供 diff 或正文未变证据，因此“只改标题” fidelity 严格判 FAIL/UNKNOWN，而非凭成功状态判 PASS。
- J06 已有 Draft Context，却同时声称对象与指令都缺失。

## 18. Memory Findings

- K01 FAIL。
- 第一轮表达“不喜欢标题使用逆袭”后，第二轮“再给我一个标题”没有应用短期偏好，而是要求 `opportunity_ref`。

## 19. Publication / Review Findings

- UI 正确显示 PublishedNote 592 为实际发布 V2，且 Current Context Card 正确。
- B06 在 30 秒后无 AI 回复；N05 返回“这篇: REFERENCE_CONTEXT_MISSING”。
- 因 Review 没有运行，exact V2、private metrics、UNKNOWN public metrics 与 Strategy Candidate 均未得到 Agent 链路验证。

## 20. Frontend Usability Findings

- 导航、资产选择和 Current Context Card 可用。
- Account selector 只显示名称，不显示 Account ID；仅凭合同中的 `8456`，普通用户无法确认对应选项。
- `REFERENCE_CONTEXT_MISSING` 仍作为主回复出现。
- Pending 的实际字段被统一显示为“必要信息”，用户不知道具体需要补什么。
- 部分请求失败后只有用户消息、状态回到“就绪”，没有可见失败解释。
- Trace 控制台无法为本批 Turn 提供可关联的新 Run，诊断可观测性不足。

## 21. Critical Defects

1. **聊天正文 URL 没有进入材料合同**：直接阻断所有真实 Research。
2. **Current Context 未稳定进入 Agent resolver**：Research、Strategy、PublishedNote 均可见但后端仍判引用缺失。
3. **Conversation capability handler 固定回复**：能力、Skill、Tool 三类问题语义不敏感且显示成功。
4. **Unsupported capability 被误判为 missing parameters**：自动发布、自动评论边界失真。
5. **静默失败**：Strategy/Review 请求可在约 30 秒后无 AI 回复、无 Pending、无失败状态。
6. **Pending 字段不可理解**：业务字段在 UI 全部退化为“必要信息”。
7. **Trace 无法关联正式前端 Turn**：Workflow/Tool/Provider 指标大量 UNKNOWN。

## 22. All Failed Cases

| Case | Failure |
|---|---|
| A03 | 未说明完整能力，返回固定欢迎语 |
| A04 | 未读取/说明真实 Skill Registry |
| A05 | 未解释真实工具能力 |
| A07 | 自动发布被误判为缺草稿/文本 |
| A08 | 自动评论被误判为缺 URL/模板/频率 |
| B01 | Profile URL 未抽取 |
| B03 | Research 已选中，但无 AI 回复或 Strategy |
| B04 | Strategy 已选中，仍为引用缺失 |
| B06 | PublishedNote 已选中，但无 AI 回复或 Review |
| C01 | Draft 已选中，仍为引用缺失 |
| D01 | Profile URL 未抽取 |
| D02 | Note URL 未抽取 |
| D03 | 三条 Profile URL 均完整保留，但全部被解释为引用缺失，未形成材料 |
| E01 | Profile Research 未启动 |
| E02 | Note Research 未启动 |
| E05 | 两个 Profile 均未启动 Research |
| G01 | Research 已选中，但没有策略结果 |
| H01 | Strategy 已选中，仍报告 Strategy/Opportunity 缺失 |
| J01 | 新版本可见，但无法从 UI 回答验证正文 hash 不变 |
| J06 | 已选 Draft，却同时判断对象缺失 |
| K01 | 短期偏好未保持 |
| L02 | Pending 后补 URL 未 Resume Research |
| M04 | 未假成功，但也未明确 Handler 不支持 |
| N05 | PublishedNote 已选中，仍报告“这篇”引用缺失 |

## 23. Evidence Index

- Eval Dataset：`docs/eval/functional_baseline_v1.jsonl`
- 完整逐条回答、transcript、状态、Pending、Trace、延迟和评分：`docs/eval/results/functional_baseline_v1_results.jsonl`
- 批次 checkpoint：`docs/eval/results/functional_baseline_v1_partial.jsonl`
- 汇总指标：`docs/eval/results/functional_baseline_v1_summary.json`
- 截图：按用户补充要求不保存。

## 24. Recommended Fix Priority

1. P0：修复聊天文本与补充材料 URL → canonical materials 的统一解析。
2. P0：修复 Current Context Card selection → Agent resolver 的引用传递，覆盖 Research/Strategy/PublishedNote。
3. P0：消除无 AI 回复、状态回到“就绪”的静默失败。
4. P1：为能力、Skill、Tool、Unsupported capability 建立真实且可解释的 Conversation response。
5. P1：Pending UI 展示具体字段与人类说明，禁止主回复暴露内部错误码。
6. P1：让 Trace 能按正式前端 Turn/Conversation 关联 Run。
7. P2：Revision 成功回复提供变更范围摘要或可见 diff，支持 fidelity 黑盒验收。

## 25. Git

- 未 commit
- 未执行 git add / reset / restore / clean / stash
- 未修改 production code、Prompt、Intent、Resolver、Handler、Workflow、Tool、Provider 或前端产品代码
- 本轮只新增 Eval Dataset、UI 驱动记录工具和结果文档
