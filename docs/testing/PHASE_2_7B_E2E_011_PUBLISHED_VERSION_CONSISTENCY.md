# Phase 2.7B E2E-011 Published Version Consistency

## Baseline

Account 8456 / Draft 2625 在执行前只有 V1=2082 与 V2=2087，Draft latest=V2。PublishedNote 592 与 PublishPackage 511 均精确绑定 DraftVersion 2087/V2；Review Artifact 2141 仍指向 PublishedNote 592 / Draft 2625。V1/V2 snapshot MD5 分别为 `8bec704aff0df1b3dbcb354da6864193`、`6af2133da2be6c46a7af710e4f0672d9`。

## Canonical V3 Attempt

创建干净 Conversation 1462，通过正式 `POST /api/agent/turns` 提交 Account 8456、Workspace Draft 2625 和“把当前草稿开头改得更直接一些，其他内容尽量保持不变。”。Turn 198 正确解析为 `CONTENT_REFINE / EXECUTE_PLAN`，启动 Run `wfr_c8c1936eff5e4db591aaf6f1269ed1f5`（DB id 2948）。没有直接调用 Workflow、Repository 或写数据库。

## Runtime Result

Run 在 Draft resolution、Opportunity resolution、Evidence retrieval 均 SUCCESS 后，于 Revision FAILED；Draft version persistence 保持 NOT_STARTED，Operation count=0。Control Semantic OBS 2207 使用 qwen3.8-flash，4483ms SUCCESS。Draft Revision OBS 2208/2209 使用全局 qwen3.8-2.4t-a95b，分别 30742ms/30759ms，均为 `Request timed out` / PROVIDER_FAILED。

## Immutability / Side Effects

失败后 Draft 2625 仍只有 V1/V2，两个 snapshot MD5 不变。PublishedNote 592 仍为 DraftVersion 2087，raw snapshot MD5 与 updated_at 不变。PublishPackage 511 仍为 DraftVersion 2087/version 2，package snapshot MD5 与 updated_at 不变。Review count/max、Candidate count/max、Operation count/max、Strategy Memory count/max 均不变；只新增预期 Conversation、Turn、WorkflowRun 与 PromptRunLog。

## Blocking Classification

该结果未触发 E2E-011 定义的版本漂移 Product Defect：没有 V3、没有持久化、没有 PublishedNote/Package/Memory 变化。阻断属于新的 Draft Revision provider execution policy/environment：当前 Revision 仍使用 strong model + 30s 全局预算并耗尽两次 structured attempts。未获授权修改 per-task routing、thinking、timeout 或 retry，因此不继续 V4 和 Review。

`ENV-010 = DRAFT REVISION STRONG MODEL 30S TIMEOUT / OPEN`。

`E2E-011 = BLOCKED BY ENV-010 / V3 NOT CREATED`。

## ENV-010 Schema Adherence RCA / Resolution

`DraftRevisionLLMResult.applied_changes` 是 required `list[str]` 且 `min_length=1`，没有默认值。调用链始终把正确的 `DraftRevisionLLMResult` 传给 `generate_structured`；Provider `_json_prompt` 追加的完整 JSON Schema 也包含该 required 字段。Qwen OpenAI-compatible 请求实际使用 `response_format={type: json_object}`，不是 native strict JSON-schema enforcement。Revision v1 领域 Prompt 仅要求结构化 JSON，没有字段级解释 `applied_changes`；OBS 2211/2212 的 sanitized candidate keys 已在 Provider candidate 层缺失该字段，中间层没有删除。

RCA 分类为 A：Pydantic/JSON Schema 正确，但在 JSON-mode Provider 下领域 Prompt 缺少 `applied_changes` 明确合同。最小修复只把 Draft Revision Prompt v1 升为 v2，要求非空字符串数组逐项描述用户要求实际应用的修改，禁止省略、空数组或模板文本；没有降低 Pydantic、增加 alias/default 或修改 Workflow。

定向回归 48 passed。正式 Turn 203 / Run `wfr_e55d2c5784d34175af5a4bd9dd123e44` 使用原反馈、Draft 2625/V2 和新 request id；OBS 2219 为 qwen3.8-flash / thinking=false / timeout 120 / attempt 1 / 10279ms / SUCCESS / is_mock=false，JSON/Pydantic/Business validation PASS。创建 V3=2112/version 3/parent 2087，Operation 305 唯一成功持久化。

Fidelity：V2/V3 title、tags、CTA 完全相同；body length 621→609；首段 MD5 改变，首段之后正文 MD5 均为 `a4d7a081523d6836c7720b1b5fc802b9`；`applied_changes` 非空并准确声明直接化开头及保留其余正文。V1/V2 hash 不变。

Regression：Backend 665 passed / 3 skipped / 18 warnings；Frontend 7/7；typecheck/build PASS。Migration=0。

`ENV-010 = RESOLVED / REAL DRAFT REVISION WORKLOAD VERIFIED / FROZEN`。

本轮不创建 V4、不执行 Review；`E2E-011 = IN PROGRESS / V3 CREATED / V4 AND REVIEW NOT EXECUTED`。

## E2E-011 Final

Baseline：Draft 2625 的 V1=2082、V2=2087、V3=2112 hashes 分别为 `8bec704aff0df1b3dbcb354da6864193`、`6af2133da2be6c46a7af710e4f0672d9`、`7f744b341e5530ad08a5c31c9bac8ad2`；PublishedNote 592 和 Package 511 均绑定 V2/2087。

V4：正式 Turn 207 / Run `wfr_7d94ebeee58f44c7b937abc973b81a1d` 使用 Draft 2625 和结尾精简反馈，Control/Resolution/Retrieval/Revision/Persistence 全部 SUCCESS。OBS 2227 为 qwen3.8-flash / `draft_revision_semantic/v2` / 6284ms / SUCCESS / is_mock=false。Operation 312 创建 V4=2114/version4/parent2112/USER_REVISION。V3/V4 title、tags、opening 及去除结尾后的正文 hash 相同；body 609→595，CTA 精简，applied_changes 准确。

核心状态：Draft current/latest=V4/2114；PublishedNote 592 仍为 V2/2087，raw hash 与 updated_at 不变；Package 511 仍为 V2/2087/version2，snapshot hash 与 updated_at 不变。

Review：干净 Conversation 1499 / Turn 208 / Run `wfr_238a01de097e41adb4d6c354bd2eefc2`，只选择 PublishedNote 592，用户未指定 V2。Runtime 同时记录 latest=2114 与 resolved published=2087；Analysis input content MD5=`06e96a2c58dd131d69eb475cee844897`，与 V2 完全相同、与 V4 的 `9e89f618066a4eff886e529635eab317` 不同。不存在 latest drift。

Review OBS 2230：qwen3.8-flash / `post_publish_review_semantic/v2` / attempt 2 / 21310ms / SUCCESS / is_mock=false；JSON/Pydantic/Business/Grounding PASS。Public count=0、UNKNOWN/{}；Private Snapshot 416 hash 不变，DM=3、WeChat=1/USER_ATTRIBUTED，其他字段 UNKNOWN。Allowlist 仍来自 resolved/authorized refs，V4 未获得 published-content 身份。

Persistence：Review Artifact 2144 / Account 8456 / PublishedNote 592 / Draft 2625 / SUCCESS，通过 PublishedNote immutable binding 可恢复 published V2/2087。Candidates 47/48 均为 PROPOSED 并指向 Review 2144；Operations 313/314/315 分别保存 Review 与两个 Candidate。Account 8456 Strategy Memory 前后均为 0。

Immutability：最终 V1/V2/V3 hashes 均与 baseline 一致；V4 新 hash=`907e98b5618f5ce256346a2acb4f56a2`。没有新 PublishedNote/Public Snapshot、没有修改 Package/Private Snapshot、没有自动发布或 Memory 写入。

Regression：本轮相关 Publication/Review targeted tests 26 passed。此前同一代码状态 Backend full 665 passed / 3 skipped / 18 warnings，Frontend 7/7、typecheck/build PASS。Migration=0。

`E2E-011 = PASS / PUBLISHED VERSION CONSISTENCY VERIFIED / FROZEN`。

未执行 E2E-012，未开始 Testing Track，未更新成功案例面试资产。

## ENV-010 Flash Policy Diagnostic

按既有 per-task execution-policy 模式增加 Draft Revision 专属可选配置，并复用统一 `LLMClient.generate_structured`、PromptRunLog 与 Adapter structured retry。容器验收配置为 qwen3.8-flash / timeout 120s / thinking=false；全局模型仍为 qwen3.8-2.4t-a95b / 30s。OpenAI-compatible SDK 继续 `max_retries=0`，Workflow 未增加 Provider retry。

定向回归 43 passed。正式 Turn 199 使用新 client request，未 Resume Run 2948；Control Semantic OBS 2210 为 flash / 5452ms / SUCCESS。Draft Revision OBS 2211/2212 均真实使用 flash，分别 8948ms/7303ms，Provider 返回结构化候选，但 Pydantic 均因必填 `applied_changes` 缺失而 VALIDATION_FAILED。JSON candidate 不能通过完整 `DraftRevisionLLMResult` 合同，因此 Business validation 与 Revision fidelity 未达到可验收状态。

Run `wfr_5f190d00041c489baa5cd96dfffe9d5b` 在 Revision FAILED，persistence NOT_STARTED，Operation=0；Draft 2625 仍只有 V1/V2，两个 snapshot hash 不变，PublishedNote 592 与 Package 511 仍精确绑定 V2。

Flash 已证明 latency 明显低于 30s，但未满足 Schema，故不能关闭 ENV-010，也不能继续 V3/V4/Review。下一步需单独决定是先做现有 Prompt/Schema adherence RCA，还是受控验证 strong + longer timeout；本轮未调用 strong+120。

Regression：Backend 663 passed / 3 skipped / 18 warnings；Frontend 7/7；typecheck/build PASS；Migration=0，Alembic 仍需最终检查。

`ENV-010 = FLASH LATENCY VERIFIED / DRAFT REVISION PYDANTIC CONTRACT FAILED / OPEN`。

`E2E-011 = BLOCKED BY ENV-010 / V3 NOT CREATED`。
