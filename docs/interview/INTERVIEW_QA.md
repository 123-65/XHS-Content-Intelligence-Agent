# 项目面试 Q&A

## Q：为什么结构化输出通过 Pydantic，还需要业务语义 Validation？

Pydantic 只能证明字段、枚举和类型合法，不能证明字段组合符合产品语义。真实 Turn 124 中，`RESEARCH + QUERY_PROFILE` 在 JSON 和 TaskSemanticFrame 上完全合法，但 Profile URL 只是 Research 输入，不是用户明确要求的第二个独立目标；该组合违反了冻结的 V1 mixed-goal contract，并最终在 Planner 才失败。

修复把第一道业务防线放在 Semantic post-parse 阶段：Workflow primary 只允许 Workflow sub-goals；非法组合记录 `POST_PARSE_BUSINESS_VALIDATION` 并复用现有 structured retry，不静默删除可能真实存在的第二目标。真实 Turn 128 首轮再次产生相同 mixed frame，OBS 捕获后第二轮得到合法 RESEARCH，Planner 随即创建 RESEARCH_V1 Run。Schema Validation 保证“形状正确”，Business Semantic Validation 保证“组合含义可执行”，Planner 则继续保留为最后的 defensive safety net。

## Q：为什么 Agent 不应该所有节点都使用同一个大模型？

模型应按 workload 匹配，而不是按 Agent 名称一刀切。真实 ENV-005 中，强模型 `qwen3.8-2.4t-a95b` 能完成相同 Semantic Prompt 和 TaskSemanticFrame Schema，但耗时约 92.5 秒；这证明合同本身可工作，却不适合每个 Turn 都要经过的实时入口。

Control Semantic 只负责 Intent、Reference、Constraint 等结构化理解，不负责 Research 分析、Strategy 或 Draft 内容质量。项目因此复用现有 per-call model override，只让它使用 `qwen3.8-flash` 并关闭 thinking；真实完整 contract 首轮 8.1 秒完成且 validation PASS。Research、Strategy、Draft、Review、Revision 仍使用默认强模型，也没有被强制关闭 thinking。这个最小路由把入口 latency 与内容质量职责分开，同时避免引入复杂动态 Router。

## Q：为什么不能让 LLM 自己生成数据库中的 source_opportunity_id？

LLM 适合做语义判断和内容生成，但不掌握数据库里的 canonical identity。真实 E2E 中，Research Query Projection 曾遗漏 Opportunity 3923，LLM 在没有合法候选 ID 的情况下生成了 `1`，随后 Repository 的 lineage validation 正确拒绝了 `Source Opportunity 不存在: 1`。

修复放在 Query boundary：把 canonical Opportunity identity 连同必要事实投影给 Strategy 上下文。没有在 Repository 猜测 ID，也没有通过容错把非法 ID 改成某个现有值。这样 LLM 负责“选哪个和怎么表达”，确定性代码负责“这个对象到底是谁”。

## Q：为什么 LLM 返回 missing_info，不应该直接让 Agent 向用户追问？

`missing_info` 是 LLM 对“还可以补充什么”的语义建议，不天然等于 Workflow 无法执行。真实案例里，用户说“根据刚才那个研究帮我做选题”，系统已经解析到 canonical Research 2862；数量和偏好只是 optional preference，但 Planner 曾把它们无条件升级为 blocker，造成过度澄清。

修复后保留原始 semantic `missing_info` 供观察和测试，但是否阻塞由确定性控制层决定：Resolver 负责 canonical reference 的 resolved、unresolved 和 ambiguous；Planner 依赖 typed Workflow Input Builder 判断 required input 能否构建。缺少 Research 或引用有歧义时仍然追问，有合法默认值的偏好缺失则直接执行。这样既利用 LLM 的语义能力，又由业务合同控制执行边界。

## Q：为什么概率性 AI Bug 不能因为第二次运行成功就关闭？

DEFECT-007 首次真实运行失败，但相同上下文的一次受控诊断首轮成功。如果只看第二次结果，很容易误判为“已经好了”。实际上后续 turn 69 又稳定复现失败，并证明问题来自模型合法输出与 Service allowlist 的合同不一致。概率性系统需要保留失败样本、attempt trace 和确定性校验结果；只有根因修复并通过真实回归，才能关闭缺陷。

## Q：为什么 Structured Retry 需要保存中间失败证据？

Retry 最终成功只说明用户请求恢复了，不代表第一次输出正确。OBS-001 会为每次 attempt 保存状态、validation layer/path、脱敏 candidate 和是否耗尽重试，因此可以区分“第一次 Pydantic invalid、第二次 valid”和“一直 provider failure”。否则中间失败会被最终成功覆盖，无法评估模型兼容性、Prompt 质量或真实失败率。

## Q：为什么用户安全错误信息和内部 RCA 信息要分开？

用户只需要稳定、安全、可行动的错误信息，不能看到 provider 原文、内部结构或凭据；工程侧则必须知道失败发生在 Provider parse、Pydantic schema 还是 post-parse business validation。项目保留统一 safe error，同时把 provider/model、attempt、validation path、expected/actual type 和脱敏 candidate 写入独立证据。这样既避免泄密，也能完成可复现的根因分析。

## Q：为什么“LLM 可见的数据范围”和“LLM 允许引用的数据范围”必须保持一致？

DEFECT-007 中，Research 2862 和 Opportunity 3923 都是 Strategy 的正式输入。模型生成的结构化输出通过 Provider/Pydantic 校验，也正确引用了 canonical `content_opportunity:3923`；但原 authorized evidence set 只有 `research_report:2862`，于是 deterministic grounding 在 post-parse 阶段拒绝了本来合法的引用。

修复原则不是放宽成“数据库里存在的 Opportunity 都能引用”，而是让 authorization 与本次可信输入对齐：只把当前 `historical_opportunities` 中的 canonical Opportunity 纳入 allowlist。既有回归验证当前输入中的 ID 可以通过，300、400、999 等未授权 ID 仍被拒绝，因此不会跨 Research、跨 Account 或凭任意数据库 ID 扩权。

DEFECT-020 补充了另一种失配：上游已经解析 PublishedNote 592、DraftVersion 2087、Private Snapshot 416 及 Strategy/Opportunity lineage，但 Workflow 没把这些 refs 传入 Analysis Tool，导致 Service allowlist 为空。修复不是关闭 validator，而是建立 Producer→Carrier→Consumer 的显式传播：Metrics/Artifact Query 产生 canonical refs，Workflow state 和 `grounding_refs` 承载，Service 对 Review 及 Candidate 全部引用做确定性子集校验。真实 allowlist 仅含本次解析的 `published_note:592`、`private_metric_snapshot:416`、`research_report:2862`、`content_opportunity:3923`，不会扫描 Account 全局或相信模型自报引用。

## Q：一次 VALIDATION_ERROR 是如何最终定位成 Grounding Authorization Bug 的？

Turn 65 最初只有统一的 `VALIDATION_ERROR`，原系统没有 structured failure evidence，无法判断失败发生在 Provider、Pydantic 还是业务校验。补齐 OBS-001 后，Turn 69 真实复现保留了逐 attempt 证据：Provider/Pydantic SUCCESS，随后 `POST_PARSE_BUSINESS_VALIDATION` FAIL，并捕获到 `content_opportunity:3923`。把它与正式输入对照后，确认模型引用合法，真正缺失的是 Service authorized evidence set 中的 Opportunity 授权。

因此修复保持最小：补齐当前正式输入的 canonical Opportunity 授权，再由成功 E2E 验证。这个链路说明可观测性不是附属日志；它把笼统错误拆成明确失败层，避免改 Prompt、放松 Schema 或绕过 Repository 等猜测式修复。

## Q：为什么统一的 Context Identity Adapter 不能假设所有业务对象都有 account_id？

E2E-003 选择 generated Opportunity 3956 时，Workspace Selection 在 LLM、Semantic 和 Planner 之前就失败了。通用 adapter 能从 Strategy、Draft 等模型直接读取 `account_id`，却把这个结构假设套到了 `ContentOpportunity`；Opportunity 实际通过 `report_id` 和 `strategy_artifact_id` 建立 lineage，并没有直接 `account_id`，因此触发 `AttributeError`。

这说明统一 identity contract 不等于统一数据库字段。最终修复使用显式 type-specific resolver：generated Opportunity 沿 Strategy lineage 读取 Account，historical Opportunity 沿 Research lineage读取 Account；Strategy、Research、Draft 等继续使用各自正式 owner。服务端始终以 canonical ownership 为准，不信任客户端传来的 `account_ref`，也没有为了接口统一给所有表冗余 `account_id`。显式 resolver 比 `hasattr` 或通用 `report_id` fallback 更安全，也更容易覆盖跨账号回归。

E2E-007 证明 Account boundary 还必须在 Agent execution 之前保护 Conversation 本身。Conversation 是 durable context owner，内含 recent references、Pending 和 workspace/context 线索；如果只在下游 Repository 查询增加 `account_id` 条件，跨账号请求仍可能先进入 Semantic、读取上下文或触发 Workflow。真实请求用 Account 1 访问 Account 8456 的 Conversation 874 时，HTTP 403 / `CONVERSATION_ACCOUNT_MISMATCH` 在 Turn reserve 前返回，Turn/Run/LLM/MCP/Operation/Artifact/Evidence 全部不变；正确 owner 随后仍能以 GENERAL_CHAT 创建 Turn 164。这种“拒绝发生在正确层级”的证据比单看 403 更强。

## Q：为什么修复后的 E2E Retry 要换 client_request_id，但不能删除旧失败请求？

`client_request_id` 是一次请求的幂等身份，相同 ID 应稳定代表同一次调用。AgentTurn 77 已记录修复前的 Workspace ownership 失败；删除或改写它会破坏 RCA 与审计证据，而复用同一 ID 则应按正式合同重放原失败，不应偷偷执行修复后的新逻辑。

产品代码修复后的验证属于一次新的测试请求，所以使用新的 request ID 创建 Turn 84，同时保留 Turn 77。这样既维持 exactly-once 风格的请求语义，也能清楚比较修复前后的行为，并在后续发现 DEFECT-009 时保留完整演进链路。

E2E-006 进一步用真实成功请求验证了 durable replay。将 Turn 163 持久化的 canonical payload 原样再次提交到正式 HTTP API，返回仍是 Turn 163 和原 Run/checkpoint；Turn/Run/PromptRunLog/MCP call/Operation/Evidence/Artifact 计数及 max ID 全部不变。因此“返回内容一样”或“响应很快”不足以证明幂等；必须联合 durable fingerprint、Turn identity、Run identity 以及无 LLM/Provider/业务副作用重放。同 key 修改 message 则返回 HTTP 409 / `REQUEST_IDENTITY_MISMATCH`，且同样零副作用。

## Q：Agent 如何解析“这个”“它”“刚才那个”这类模糊指代？

不让 LLM 直接决定数据库对象。真实 Turn 84 中，Semantic 正确识别 CONTENT_CREATE，但把“这个”表示为 UNKNOWN reference；旧 Resolver 因 UNKNOWN 没有类型映射，在查看 Workspace Opportunity 3956 前就返回了 `REFERENCE_CONTEXT_MISSING`。

修复后由代码根据 Intent 得到 expected reference type：CONTENT_CREATE 需要 Opportunity、CONTENT_STRATEGY 需要 Research、CONTENT_REFINE 需要 Draft。只有 reference 属于有限的 context-dependent 表达时，才按 `explicit > workspace > pending > active > recent > history` 查找当前层的类型匹配候选；唯一候选经过 canonical Account ownership 验证后解析，多候选则澄清，错误类型不能替代。Turn 91 因此把“这个”确定性解析为 Workspace Opportunity 3956，而不是让模型生成数据库 ID。

Profile URL 还需要区分“外部显式材料”和“内部 canonical identity”。DEFECT-015 的 Turn 129 已明确提交唯一授权 Profile URL，但 Semantic 同时生成 `PROFILE / 该账号` 后，旧 Resolver 只接受已有 `ACCOUNT ObjectRef`，形成“必须先有 Account 才能采集、但 Account 又要由采集建立”的循环。修复后，当前 Turn 的授权 Profile material 可以在最高优先级消解这类语言引用，但只记录“reference 已由 material 定位”，绝不伪造 Account ObjectRef、数据库行或采集成功。唯一性、冲突和账号边界仍由代码验证，canonical Account identity 仍只能在 `collection_accounts` 成功后建立。

## Q：为什么 Workspace 中同时有多个类型的对象，并不一定意味着“这个”有歧义？

歧义应在 Workflow Contract 要求的类型内判断，而不是把 Workspace 所有对象混在一起。CONTENT_CREATE 的 required reference 是 Opportunity，所以 Workspace 同时存在 Research 和 Opportunity 时，只有 Opportunity 是候选；CONTENT_STRATEGY 则只看 Research，CONTENT_REFINE 只看 Draft。

只有同一优先级中存在多个可信且同类型的合理候选时才标记 ambiguous。这样既避免跨类型误选，也保持 Context priority：明确的 ordinal/explicit 引用仍优先，invalid explicit 也不会偷偷 fallback 到 Workspace 掩盖用户错误。

## Q：为什么 EvidenceRef、业务上下文和可检索 Evidence 不能混为一谈？

DEFECT-010 中，Strategy EvidenceRef 是较宽的 grounding/reference contract：`research_report:2862` 表示研究来源，`content_opportunity:3923` 表示 Generated Opportunity 3956 的来源和授权。它们能证明“这个选题从哪里来”，但不能直接投影成供 Draft 使用的事实正文。真正的 Retrieval Evidence 合同只有 NOTE、COMMENT、ACCOUNT。

旧 Workflow 把 Opportunity 上全部宽引用直接转换成窄 retrieval input，导致合法的 `content_opportunity:3923` 被送入不支持它的 retrieval tool。修复没有扩展 retrieval 类型，也没有删除 lineage，而是在 Workflow assembly 做 typed partition：Strategy 13 和 Generated Opportunity 3956 保持 Business Context，Research 2862 和 Source Opportunity 3923 保持 lineage/grounding，Research canonical projection 中的 ACCOUNT/NOTE/COMMENT 才进入 EvidenceBundle。真实重试因此使用 `ACCOUNT:2914` 与 `NOTE:10998/10999/11000` 完成 Draft，同时保留 3923 的来源关系。

## Q：为什么不能遇到 Retrieval Tool 不认识的 ref 就直接跳过？

Silent skip 会把合同错误变成上下文缺失：Workflow 可能表面成功，Draft 却没有读到本应使用的事实依据，后续 Grounding 和审计也无法判断证据为什么消失。DEFECT-010 的正确处理不是 `if unsupported: continue`，而是对已知引用做正式分类：`research_report` 和 `content_opportunity` 进入 lineage/grounding 分支，NOTE/COMMENT/ACCOUNT 进入 retrieval 分支。

真正未知的类型仍必须 fail fast；Opportunity 声明的事实引用如果不属于当前 Research projection，也必须拒绝。这样既不会误伤合法 lineage，也不会通过过滤掩盖新类型、跨 Research 或跨 Account 的扩权问题。

## Q：为什么同一个 Evidence Contract Bug 会在 Creation 修复后继续出现在 Refinement？

因为 Creation 和 Refinement 是兄弟 Workflow，过去各自维护了一份相似但独立的 Evidence assembly。DEFECT-010 只在 Creation 中把宽 Strategy refs 分成 grounding 与 retrieval；Refinement 仍保留旧实现，于是同一个 `content_opportunity` 在 Creation 已能正确保留为 lineage，却在 Refinement 中继续被误送进 retrieval tool。单独验证 Creation 只能证明一个调用方正确，不能证明合同在所有调用方一致。

修复方式是提取一个小型 typed partition，让两条 Workflow 复用同一分类规则，同时增加 contract parity 覆盖：相同 mixed refs 必须在两侧得到相同 grounding 和 retrieval 结果。共享的是稳定的语义边界，不是整个 Workflow；版本解析、生成、修订和持久化仍各自保持独立。这样能减少语义漂移，同时避免把两个业务流程强行耦合成一个大抽象。

## Q：为什么 Context Resolver 不能依赖 LLM 每次都输出 SemanticReference？

Turn 96 和 Turn 103 使用完全相同的文本与 Workspace Draft 2625，但真实 LLM 一次输出 `ACTIVE_DRAFT / 这个开头`，另一次返回 `references=[]`。旧 Resolver 只遍历 Semantic references，导致概率性字段决定已经过服务端 canonical ownership 校验的业务对象是否“存在”：前者 READY，后者错误追问 `draft_ref`。

SemanticReference 应是语义信号，而不是 Workspace 存在性的唯一来源。修复后，Resolver 根据 Intent 的 required type，在不存在显式冲突时使用唯一可信 explicit/workspace candidate；CONTENT_REFINE 因此只接受唯一 Draft。显式非法引用仍优先阻断，多候选仍澄清，跨账号仍拒绝，错误类型也不能替代 Draft。这样由 LLM 理解语言，由确定性控制层保证业务身份稳定。

## Q：为什么 Draft 修改使用 immutable version，而不是覆盖原内容？

真实 E2E-004 在同一 Draft Root 2625 上保留 V1 2082，并新增 V2 2087；V2 的 `parent_version_ref=2082`、`version=2`、`created_from=USER_REVISION`，V1 正文 MD5 仍保持 `4004ba8f766c34feffa900b8e38af716`。Product Read 同时返回两个版本，并把 V2 标为 latest。

不可变版本让修改可审计、可比较、可回滚，也使发布动作能够绑定某个精确版本，而不是绑定会被后续编辑改变的“当前内容”。Exact Parent 还能防止并发或 stale revision 静默分叉；Operation Ledger 则保证同一次持久化操作不会重复创建多个 V2。

E2E-011 给出了发布后最关键的反例：用户实际发布的是 V2/2087，之后同一 Draft Root 又 append-only 演进出 V3/2112 和 V4/2114，此时 current/latest 已是 V4。新的 Post Publish Review 没有根据 `draft_id` 调 `get_latest_version()`，而是从 PublishedNote 592 的 immutable `draft_version_id=2087` 恢复 V2；运行时同时报告 latest=2114、resolved published=2087，送入 Analysis 的 content MD5 与 V2 完全一致、与 V4 不同。Review 2144 继续绑定 PublishedNote 592，因此也可恢复 actual published V2。如果只保存 Draft Root，复盘会把后续编辑稿误当成真实发布内容，指标归因、策略候选和审计链都会错位。

## Q：为什么最小 health/smoke PASS 不能证明真实 Provider workload 可用？

Phase 2.7B 的 Qwen 最小 smoke 只要求返回一个布尔字段，schema 只有 1 个 property、约 168 个字符，真实调用约 5.7 秒成功；同一 provider/model 下，Control Semantic 使用 13 个字段、约 3990 个字符的 TaskSemanticFrame schema，并附带完整语义规则，连续两次 adapter attempt 都约 102 秒后 timeout。健康检查和最小 smoke 证明的是连接、鉴权与最小 structured-output 能力，不证明复杂业务 schema 能在生产 timeout 内完成。

MCP 也暴露了同一类分层误判：`/mcp` 可达且 `tools/list` 返回 18 个工具，只证明 HTTP/MCP 控制面与工具注册正常；`check_login_status` 还要在服务端启动 bundled Chrome、建立 CDP/rod browser、创建页面并执行登录态检查。真实诊断中前者一直 HTTP 200，后者却曾在 MCP 内部返回 `context deadline exceeded`。因此 Provider health 必须至少覆盖一个安全的依赖型工具调用，并分别记录 transport、RPC、browser/page 与业务结果；端口和工具清单不能替代数据面健康。正确工作目录重启并完成 browser 冷启动后，canonical Provider 才在约 20 秒返回登录成功。

这次还暴露了 retry 分层问题：SDK client timeout 为 30 秒且内部 `max_retries=2`，所以 adapter 观测到的一次 attempt 实际最多包含 3 次 HTTP 尝试；外层又有两次 attempt，最终一个 Turn 接近 205 秒。可靠验收必须覆盖真实 Prompt、真实 Schema、真实 timeout/retry 边界，并让一个层级明确拥有 retry，否则 smoke latency 和业务 latency 不在同一个合同层面。

## Q：如何验收跨 HTTP 请求的 Workflow Resume，并避免把“命中同一 Run”误判成完整成功？

真实 E2E-005 先用 Turn 144 只提交 Profile URL，`RESEARCH_V1` 完成账号采集后在 Evidence Gate 进入 `WAITING_USER`：Run、checkpoint=3、Pending Interaction 和 Conversation active pending 全部持久化。Turn 145 是新的 `POST /api/agent/turns`，只补 Note URL，没有传 run_ref，也没有直接调用 Runtime；Control 层从 Conversation Pending 找回同一 Run，checkpoint 3→5，execution mode 变为 RESUME。恢复后的 state 显示 `growth_context` 和 `collection_accounts` 都是 SKIPPED，账号证据 ref 保持 2914，Operation 0→0，Artifact 和 Evidence 数量不变，因此能够证明没有新建第二个 Run，也没有重放已完成副作用。

但这次不能宣称 Resume PASS：Turn 2 的 3 条可信 Note URL 在 Semantic Frame 合并后变成 6 条，其中 3 条是模型重建的非 URL 值；Resume builder 直接采用 `frame.note_urls`，最终在 Provider 调用前被 `CollectXhsNotesInput` 拒绝，Run 以 `WORKFLOW_RESUME_EXECUTION_ERROR` 失败。Pending 虽从 Run 和 Conversation 清空，也只说明它被消费/清理，不代表业务完成。完整验收必须同时满足 same run_ref、checkpoint 前进、已完成 step 不重跑、operation/artifact 不重复、Pending 清理以及最终 Workflow 成功；任何一项缺失都应保留失败结论。

修复后的 Turn 150/151 补齐了材料权威边界的真实证据：当前 Turn 的 3 条 structured Note material 经同 Account 的 `USER_PROVIDED CollectionAccessScope` 确认后，覆盖而不是 union Semantic 重建值。同一 Run 从 checkpoint 3 前进到 5，`growth_context` 和 `collection_accounts` 均为 SKIPPED，`collection_notes=SUCCESS`，processed URL 与授权 URL 逐条一致，且 Operation/Artifact/Evidence 计数无重复。这证明 DEFECT-013 的 material authority 路径已修复，但仍不能宣称 E2E Resume PASS：后续 analysis Provider 两次超时，Workflow 最终 FAILED。因此验收必须分层：先确认 durable Pending、same run、checkpoint、authoritative material boundary、completed-step no replay 和 idempotent side effects，再单独要求后续业务 Workflow 完成；新失败应登记为独立 ENV-008，不回写成 DEFECT-013。

## Q：为什么缺失的私域指标不能默认成 0？测试 fixture 超出产品字段限制时应该怎么办？

UNKNOWN 表示没有证据，0 表示用户明确测量或归因后确认结果为零，两者会导致完全不同的转化率、复盘和策略结论。E2E-009 的真实链路先读取到 Private Metrics UNKNOWN；用户随后只提交 DM=3、微信新增=1，canonical read 只返回这两个 `USER_ATTRIBUTED` 值，咨询、成交和收入继续为 null。底层兼容列虽然保存 0，但系统以 `provided_fields` 恢复领域语义，避免把存储默认值污染成业务事实；显式提交 dm_count=0 则会保留为真实 0。

验收最初使用的 fixture label 长度超过既有 VARCHAR(16)。这个字符串没有产品业务价值，因此不应为了测试方便新增 migration；正确做法是把 fixture 调整为合法的 `E2E009_ACCEPT`，保留产品约束，再通过正式 HTTP 验证。只有真实业务需求无法被现有 schema 表达时，才应扩大数据库字段。

## Q：为什么 SDK Retry 和业务 Adapter Retry 不能同时无控制地开启？

ENV-004 中，SDK timeout 是 30 秒且 `max_retries=2`，所以一个逻辑上的 adapter attempt 最多包含 3 次不可见 HTTP 请求；adapter 自己又允许 2 次 structured attempt，最坏会形成 6 次 Provider 请求。Agent 和 OBS-001 只看到 2 个 logical attempts，却承受约 205 秒延迟，同时放大成本、限流风险和故障恢复时间，单次 evidence 也无法直接表达内部三次请求。

修复后由 adapter 成为唯一 retry owner：SDK `max_retries=0`，每个 adapter attempt 精确对应一次 HTTP 请求；adapter 统一记录 attempt number、失败类型和 retry_exhausted。回归证明两轮 timeout 总调用数从最坏 6 次收敛为 2 次，首轮成功只有 1 次请求，timeout 后成功则留下 `PROVIDER_FAILED → SUCCESS` 的完整证据。这样重试策略、可观测性和成本边界才处于同一个控制层。

ENV-008 进一步说明 timeout 必须按任务层级理解。Research Analysis 使用默认强模型 `qwen3.8-2.4t-a95b`，约 4K 字符事实 evidence 叠加约 10.6K 字符 structured schema，两个 logical attempt 都在约 30.8 秒触发同一 request deadline。SDK retry 仍为 0，所以这不是 retry amplification；历史上同一强模型的 structured diagnostic 约 92.5 秒才成功，说明“模型可完成”与“共享 30 秒 deadline 适合该任务”是两个问题。Control Semantic 属实时入口，Research Analysis 是允许更慢但仍需明确上限的重任务；应先定义业务 latency budget，再决定 task-specific timeout、model routing 或 schema/payload 优化，而不是看到 timeout 就同时改多个变量。

真实修复验收又补了一层边界：系统没有把全局 timeout 改成 120 秒，而是只给 Research Analysis 一个有限的 120 秒 request budget；Control Semantic 仍是 flash+30 秒，其他调用仍默认 30 秒。这个分层在运行时和自动回归都得到验证，但真实强模型 Analysis 首轮 104.7 秒返回 connection error，第二轮 120.7 秒仍 timeout，未进入 structured validation。这说明“正确分层 timeout”是必要的工程修复，却不等于业务 workload 已经达标；达到有限上限后应停止继续加 timeout，改为独立评估 Research 专属模型路由或 Prompt/Schema 优化。

模型路由还必须使用节点自身的完整 workload 验证，不能把另一个节点的成功直接外推。`qwen3.8-flash` 在 Control Semantic 约 8.1 秒成功，但当它复用 Research Analysis 的 3 Note+1 Account evidence、约 10.6K 字符 schema 和同一 grounding validator 时，唯一调用在 121.3 秒返回 Provider failure，连 structured parse 都未到达。因此不能得出“小模型更好”或“flash 适合所有 Agent node”；正确结论是每个 node 都有自己的 latency、structured workload、quality 和 reliability contract，per-task routing 只能在该 node 的真实合同下通过后才生效。

后续 thinking-mode 隔离诊断表明，模型名还不是完整路由合同。在保持同一 Flash 模型、Evidence、Prompt、Schema、120 秒 timeout 和单次 attempt 不变时，仅显式设置 `enable_thinking=false`，Research Analysis 便从 121.3 秒 Provider failure 变为 20.575 秒 SUCCESS，且 JSON parse、Pydantic 的 10 个顶层 section 和 deterministic grounding 全部通过。因此 per-task execution policy 应同时绑定 model、thinking mode、timeout、retry policy 与 structured contract；先隔离运行策略变量，再决定是否优化 Prompt/Schema。

生产落地后还必须用完整 Workflow 重新验证，不能把隔离 diagnostic 当成 E2E 结论。本次 Research-only Flash + thinking=false + 120s 策略在真实 Pending/Resume 路径中使用同一 3 Note+1 Account workload：OBS 2150 首轮 27.274 秒 SUCCESS，`CompetitorSemanticResult` 与 grounding 通过，Workflow 继续创建 Research Artifact 2949 并以 `PARTIAL_SUCCESS` 结束。这说明 execution policy 的验收要同时覆盖运行时配置、真实负载、structured/grounding 合同、下游 Artifact 和幂等副作用。

Post Publish Review 的真实验收再次印证节点级策略：默认 strong+30s 连续 timeout，Review-only `qwen3.8-flash + thinking=false + 120s` 在 OBS 2206 首轮 21.607 秒完成 JSON/Pydantic/grounding，并继续创建 Review 2141 和 PROPOSED Candidate 43/44。但 Flash 成功不是唯一结论；同一轮还要证明 Public UNKNOWN 未被伪造为 0、Private 3/1 保持 USER_ATTRIBUTED、SDK retry=0 且 durable Memory 不变。

Draft Revision 又证明“更快”仍不等于“适合”：strong+30s 两次 timeout 后，Revision-only Flash 把响应降到 7～9 秒，却连续遗漏 required `applied_changes`。RCA 发现 Pydantic 与追加的 JSON Schema 都正确，但 Qwen OpenAI-compatible 路径只是 `response_format=json_object`，并非 native strict schema；领域 Prompt 只写“结构化 JSON”，没有解释该必填字段。Prompt v1→v2 明确要求非空、真实的 `applied_changes` 后，OBS 2219 使用同一 Flash 首轮 10.279 秒完成 Schema，V3=2112 以 parent=2087 追加成功。确定性 fidelity 对比显示 title/tags/CTA 不变、首段改变、首段之后正文 hash 完全一致。因此节点模型验收必须同时覆盖 latency、schema adherence、business validation、task fidelity 与不可变持久化。
# 为什么 Route 存在不等于 Product Entry 已完成？

Detail route 只解决“已知 canonical ID 时如何展示”，没有解决普通用户如何发现对象。DEFECT-026 的真实缺口是只有 Research/Strategy/Draft/Publication detail route，却没有 account-scoped index 与导航，用户只能手输内部 ID。最终闭环是 Account → 分页轻量 List → Object → Detail；List API 必须在 SQL 层按 Account 过滤、限制 page_size，并只返回摘要，避免重演 `/accounts` 6.6MB 的无界返回。前端持久化 Account 只恢复用户选择，真正 ownership 仍由 backend 校验。

# Phase B1 Conversational Agent Runtime

## Q：为什么把 12-Intent 硬路由改成 Conversational Agent + High-Level Tools？

十二类 Intent 同时承担自然语言理解和执行路由时，普通聊天、能力询问、上下文省略和外部 URL 很容易被迫塞进不合适的枚举，随后由 Planner 放大成错误执行。B1 让 Pydantic AI Agent 直接结合最近 20 条对话、当前材料和可信 workspace 决定直接回答或选择五个高层工具；确定性的账号归属、对象 identity、Workflow 输入和执行顺序仍由代码控制。Intent 只保留为 API 兼容与 trace 标签，不再是模型调用前的硬门。

## Q：为什么不把 17 个 Domain Tools 全部开放给大模型？

Domain Tools 包含持久化、证据读取、采集和业务状态变化，把它们全部开放会让模型同时负责步骤顺序、identity 和副作用边界。B1 只暴露五个只接收 `goal` 或 `instruction` 的高层工具；它们从 server-owned deps 取得账号与对象，并进入已有 Workflow。模型负责选择业务能力，Workflow 继续以硬编码且校验过的顺序调用 Domain Tools，从而同时保留自然语言弹性和业务确定性。

## Q：Conversation History 为什么和 Workspace Context 必须分开？

History 是用户与助手可见文本，用来理解“再短一点”、偏好和上一轮追问；Workspace 是经过账号归属验证的 canonical object identity。若把两者混合，用户文本可能被误当成数据库授权，完整 Artifact 也会造成 prompt 膨胀。实现中 History 只重建 `UserPromptPart` 和 `TextPart`，Workspace 则通过 typed deps 注入 compact ref/summary；正文只由 Workflow 在需要时读取。

## Q：为什么 Tool FAILED 不能被 LLM 最终回复覆盖成 SUCCESS？

LLM 生成的是表达，不是执行事实。Provider 未配置、Workflow 校验失败或 durable run 等待用户时，即使模型随后生成“已完成”，也不能改变真实状态。B1 的 `TurnExecutionLedger` 记录结构化 `WorkflowToolOutcome`，`ConversationResponseMapper` 以最后一次真实工具结果覆盖模型直接回复，确保 `FAILED`、`WAITING_USER`、run ref、artifact ref 和安全错误码与运行时一致，避免 fake success。

# Phase B1.1 Conversation / Workflow Tool Arbitration

## Q：为什么 Agent 能正确调用 Tool，还不代表 Tool Calling 设计正确？

“该调用时调用正确”只覆盖了召回，不覆盖误触发。真实浏览器里，Agent 能正确运行 Research、Strategy、Creation、Refinement 和 Review，但在“你是怎么知道的”“你有记忆吗”“现在起你叫张三”等普通对话中也会选择 Workflow。工具本身执行正确，整条产品行为仍然错误，因为用户没有授权本轮产生业务副作用。Tool Calling 必须同时衡量正确调用和不必要调用；B1.1 因此新增 `Unnecessary Tool Call Rate` 与 `Tool Call Precision`，并把普通聊天的目标定为零 Workflow Tool 可见、零 Run。

## Q：为什么始终向模型暴露所有 Workflow Tool 会导致 over-trigger？

Tool schema 不只是能力说明，也是模型下一步行为的强提示。历史里只要出现 Research、Strategy、Draft 或 Review，对应工具长期可见就会放大旧上下文，把解释、能力询问、persona 或 memory 问题误读为继续执行。仅靠 description 和失败后的 `ModelRetry` 仍属于事后纠错，而且工具可能已经进入等待或持久化路径。B1.1 在模型选工具之前使用 Pydantic AI `FilteredToolset`：CONVERSATION 时五个 Workflow Tool 全部不可见，BUSINESS_ACTION 时才开放现有 Toolset，从可行动作空间上消除误调用。

B2 又把 BUSINESS_ACTION 的“五个全开”收紧为 capability-based candidate set：当前材料、可信对象、lineage 和 Pending 只决定工具能否安全消费输入，不判断用户 Intent。D03 的三条当前 Profile material 因而只让 `run_research` 可见；历史 Research、Strategy 或 Draft 不再吞掉用户刚提交的材料。

## Q：为什么采用 Conversation vs Business Action Gate，而不是恢复 12 Intent Router？

十二类 Intent Router 同时承担语义分类、Workflow 选择和执行规划，会把普通聊天强塞进业务枚举，并重新引入 B1 已移除的硬路由耦合。ExecutionGate 只回答一个更窄的问题：“当前最新 Turn 是否授权调用业务工具？”输出只有 `CONVERSATION` 或 `BUSINESS_ACTION`，低于 0.75 统一 fail closed 到 CONVERSATION。它不使用 `TaskSemanticFrame`、`DeterministicPlanner` 或旧 Intent enum；具体调用 Research、Strategy、Creation、Refinement 还是 Review，仍由 Conversational Agent 在五个高层工具中选择。

## Q：为什么 Gate 只判断是否允许调用工具，而让 Agent 决定具体 Tool？

权限判断需要稳定、保守和低复杂度，具体业务选择则需要结合对话历史、代词、当前材料和可信 workspace。若 Gate 同时输出具体 Workflow，它就会演化成第二套 Router，并与 Agent 的工具语义重复。B1.1 只给 Gate 最新用户文本、当前材料类型、workspace object type、recent business context type 和 active pending type；完整 History 继续由 Conversational Agent 使用。这样 Gate 控制副作用边界，Agent 保留自然语言选择能力，Workflow 和 Domain Tool 继续维护确定性的身份、权限与执行顺序。

## Q：为什么 Tool Eligibility 不等同于 Intent Router？

Intent Router 根据自然语言预测“用户想做什么”；Tool Eligibility 不读研究、写作、复盘等关键词，只验证“这个工具能否消费服务器已经确认的输入”。例如 Research Artifact 只让 Strategy 具备候选资格，Draft 只让 Refinement 具备候选资格；它们都不会强迫执行。若多个工具同时满足客观前置条件，最终选择仍由 LLM 根据 latest user text、follow-up 和代词指向完成。

## Q：为什么 Current Turn Material 应高于 Recent Context？

Current Turn Material 是用户刚刚显式提交且进入本轮授权 scope 的输入；Recent Context 只是历史任务留下的可信对象。如果三条当前 Profile 与历史 Draft 同时存在，却仍开放 Refinement，模型可能忽略新输入去修改旧草稿。B2 因而先按当前材料的消费能力过滤：只有能消费全部未消费材料的工具进入候选集；没有当前材料时，才使用 Workspace/Recent object eligibility。

## Q：如何通过 Tool Capability Contract 避免不断增加误路由 if/else？

每个高层工具声明 `accepts_current_materials`、`eligible_context` 和 `bootstrap_without_material`，统一 policy 根据集合兼容性计算候选。新增材料类型或工具时扩展声明和矩阵测试，不在五个 Tool 内分别解析自然语言。`_validate_tool_selection` 只保留 object/material/Pending 的 objective invariant guard，语义继续属于 ExecutionGate 与 LLM。

## Q：为什么 deps 中有数据，不代表 LLM 能看到？

Pydantic AI 的 deps 是应用侧依赖注入，默认不会把整个 Python 对象自动序列化进 prompt。旧实现虽然在 deps 中保存了 current materials、recent context 和 pending identity，但 runtime instructions 只手工投影了 URL 列表和少量布尔值。B2 改为由同一个 `CanonicalTurnContext` 输出类型、数量、来源、可信对象类型、Pending 和候选工具；真实 URL 与 refs 仍只留在 deps/Workflow payload 中。

