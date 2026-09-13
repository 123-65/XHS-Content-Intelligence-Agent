# 第 5.5.1 content_draft_v2 Slot 级 Token Budget 统计字段落地报告

## 一、我这一步做了什么

本次只完成第 5.5.1：把第 5.4 设计好的 Token Budget 预算规则，落到 `content_draft_v2` 的上下文构建链路里。

简单说，就是现在每个上下文槽位在构建完成后，都会带上一份 `budget_meta` 预算元数据。它会记录这个槽位的名称、来源、中文来源说明、字符数、粗略 token 数、预算上限、是否超预算、是否必需、是否可压缩、是否可截断、中文状态说明、是否包含硬编码领域词等信息。

本次只做统计和记录，不做压缩、不做 Top-K、不改 prompt 文案、不新增数据库字段。

## 二、为什么要做这一步

第 5.4 已经设计了每个 Slot 的预算，例如 `SYSTEM_RULES` 300 token、`ACCOUNT_PROFILE` 500 token、`COMPETITOR_EVIDENCE` 1200 token。

但如果这些预算只停留在文档里，系统运行时仍然只能看到“最终 prompt 大概多长”，看不到到底是哪一个 slot 变长了、哪个 slot 超预算了、哪个 slot 后续应该被压缩。

所以第 5.5.1 的意义是：先让系统能记录 slot 级预算数据。只有能记录，后续第 5.5.2 才能知道应该优先压缩谁、Top-K 谁、截断谁。

## 三、我新增 / 修改了哪些文件

本次修改文件：

- `backend/app/context/context_budget.py`
- `backend/app/context/context_slots.py`
- `backend/app/context/context_builder.py`
- `backend/app/context/context_usage_logger.py`
- `backend/app/services/content_draft_v2_sev.py`
- `backend/tests/test_context_engineering.py`
- `backend/tests/test_content_draft_v2.py`

本次新增文件：

- `backend/tests/test_context_budget.py`
- `docs/context_budget_5_5_1_implementation_report.md`

## 四、每个文件改了什么

### 1. `backend/app/context/context_budget.py`

新增了第 5.4 设计的 12 个 Slot 预算配置 `SLOT_BUDGETS`。

新增了硬编码领域词列表 `HARDCODED_DOMAIN_TERMS`。

新增了三个核心函数：

- `rough_token_count`
- `contains_hardcoded_domain_terms`
- `build_slot_budget_meta`

同时保留原有整体任务预算逻辑 `ContextBudgetManager`，没有删除原有功能。

这次也补充了中文可读字段：

- `source_label`：来源的中文说明。
- `priority_label`：优先级的中文说明。
- `data_status_label`：数据状态的中文说明。
- `missing_policy_label`：缺失策略的中文说明。
- `description`：当前槽位用途的中文说明。

### 2. `backend/app/context/context_slots.py`

补齐第 5.3 / 第 5.4 已设计但代码枚举里还没有的 Slot：

- `DOMAIN_PROFILE`
- `COMPETITOR_EVIDENCE`
- `COMMENT_INSIGHT`
- `DRAFT_CONTENT`

这样后续实现这些 Slot 时，可以直接使用统一枚举。

### 3. `backend/app/context/context_builder.py`

在 `ContextManager._prepare_slot` 中，为每个构建后的槽位自动生成 `budget_meta`，并放入槽位的 `metadata`。

这一步让所有经过 `ContextManager` 的上下文槽位都能自动获得预算统计字段。

### 4. `backend/app/context/context_usage_logger.py`

在 `slot_token_breakdown` 里额外记录：

- `budget_tokens`
- `over_budget`

同时，槽位的完整 `budget_meta` 会通过已有的 `ContextSlotLog.metadata_payload` JSON 字段保存，不需要新增数据库字段。

### 5. `backend/app/services/content_draft_v2_sev.py`

在 `content_draft_v2` 构建上下文槽位时补充来源信息。程序字段仍使用英文枚举值，方便代码稳定；同时在 `budget_meta` 中补充中文标签，方便小白阅读。

示例：

- `SYSTEM_RULES`：程序来源值是 `prompt_template`，中文来源说明是“提示词模板”。
- `ACCOUNT_PROFILE`：程序来源值是 `account_profile`，中文来源说明是“账号画像”。
- `WORKFLOW_STATE`：程序来源值是 `content_experiment_v2`，中文来源说明是“内容实验 V2”。
- `OUTPUT_SCHEMA`：程序来源值是 `schema_model`，中文来源说明是“结构化输出模型”。
- `STRATEGY_MEMORY`：程序来源值是 `strategy_memory`，中文来源说明是“策略记忆”。

同时在 PromptRunLog 的 `_context` 里增加 `slot_budget_summary`，方便从 PromptRunLog 侧快速看到每个 slot 的预算摘要。

没有修改 prompt 文案，没有修改 LLMClient。

### 6. `backend/tests/test_context_budget.py`

新增预算工具函数测试，覆盖：

- `rough_token_count` 返回正整数。
- 12 个 Slot 都有预算配置。
- `build_slot_budget_meta` 能计算字符数、粗略 token、预算上限、是否超预算。
- 超预算时只标记，不压缩、不截断内容。
- 硬编码领域词命中时 `contains_hardcoded_domain_terms=true`。

### 7. `backend/tests/test_context_engineering.py`

补充断言：`ContextManager.build()` 之后，每个上下文槽位都有 `metadata["budget_meta"]`。

### 8. `backend/tests/test_content_draft_v2.py`

补充集成断言：生成草稿后，`PromptRunLog.input_payload["_context"]["slot_budget_summary"]` 和 `ContextSlotLog.metadata_payload["budget_meta"]` 中能看到槽位级预算字段。

## 五、重要函数怎么设计

### 1. `SLOT_BUDGETS`

`SLOT_BUDGETS` 是第 5.4 预算设计在代码里的第一版配置。

每个 slot 至少包含：

- `budget_tokens`
- `required`
- `compressible`
- `trimmable`
- `priority`
- `missing_policy`
- `description`

例如：

- `SYSTEM_RULES`：300 token，必须存在，不可压缩，不可截断。
- `ACCOUNT_PROFILE`：500 token，必须存在，可压缩，可截断。
- `COMPETITOR_EVIDENCE`：1200 token，可压缩，可截断，后续适合 Top-K。
- `OUTPUT_SCHEMA`：800 token，必须存在，不可压缩，不可截断。

### 2. `rough_token_count`

作用：粗略估算一段文本的 token 数。

设计规则：

- 中文约 1.5 个字符算 1 token。
- 英文和符号约 4 个字符算 1 token。
- 不引入 tokenizer 第三方依赖。
- 结果只用于预算判断，不代表真实模型 tokenizer 结果。

### 3. `contains_hardcoded_domain_terms`

作用：判断上下文文本里是否包含当前 demo 赛道的硬编码领域词。

例如：

- `大学生`
- `双非`
- `AI Agent`
- `项目`
- `简历`
- `面试`
- `求职`
- `学习路线`

注意：本次只是标记，不替换、不报错。比如出现 `Agent` 时，只会记录 `contains_hardcoded_domain_terms=true`，不会阻断流程。

### 4. `build_slot_budget_meta`

作用：为单个 slot 生成预算元数据。

它会计算：

- 当前 slot 的字符数。
- 当前 slot 的粗略 token 数。
- 当前 slot 的预算上限。
- 是否超预算。
- 是否必需。
- 是否允许压缩。
- 是否允许截断。
- 是否包含硬编码领域词。
- 超预算或缺失时的 warning。
- 来源、优先级、数据状态、缺失策略的中文说明。

如果 slot 超预算，本次只记录：

```text
over_budget = true
warning = "当前 slot 超过预算，后续第 5.5 再处理压缩或 Top-K"
```

不会截断原文，不会摘要，不会删除字段。

## 六、重要字段是什么意思

- `slot_name`：当前上下文槽位名称，例如 `system_rules`、`account_profile`。
- `source`：当前槽位的程序来源值，例如 `prompt_template`、`account_profile`、`schema_model`。
- `source_label`：当前槽位来源的中文说明，例如“提示词模板”“账号画像”“结构化输出模型”。
- `chars`：当前槽位的字符数。
- `rough_tokens`：当前槽位的粗略 token 数。
- `budget_tokens`：当前槽位的预算上限。
- `over_budget`：当前槽位是否超过预算。
- `priority`：当前槽位的程序优先级值，例如 `P0_REQUIRED`、`P1_EVIDENCE`。
- `priority_label`：当前槽位优先级的中文说明，例如“P0 必须保留”“P1 上游证据”。
- `required`：当前槽位是否必须存在。
- `compressible`：当前槽位是否允许后续摘要压缩。
- `trimmable`：当前槽位是否允许后续截断。
- `compressed`：当前槽位本次是否被压缩。本阶段不做压缩，所以默认是 `false`。
- `truncated`：当前槽位本次是否被截断。如果已有整体预算机制裁剪了槽位，会标记为 `true`。
- `data_status`：数据状态的程序值，例如 `REAL`、`PARTIAL`、`NOT_PROVIDED`。
- `data_status_label`：数据状态的中文说明，例如“真实数据”“部分数据”“未提供”。
- `contains_hardcoded_domain_terms`：是否包含硬编码领域词。
- `source_version`：来源版本，例如 prompt 版本或 schema 名称。
- `missing_policy`：缺失处理策略的程序值，例如 `BLOCK`、`DATA_NOT_PROVIDED`。
- `missing_policy_label`：缺失处理策略的中文说明，例如“缺失时阻断”“允许继续并标记为未提供数据”。
- `description`：当前槽位用途的中文说明。
- `warning`：预算异常提示，例如超预算、必需 slot 缺失等。

## 七、数据流怎么走

本次落地后的数据流是：

```text
content_draft_v2 服务
→ 创建上下文槽位
→ 上下文管理器 / 上下文构建器
→ 每个槽位渲染为文本
→ build_slot_budget_meta 计算预算元数据
→ budget_meta 写入槽位 metadata
→ 提示词运行日志中记录槽位预算摘要
→ 上下文使用日志记录器保存快照
→ 上下文快照中记录槽位预算总览
→ 上下文槽位日志中记录完整 budget_meta
→ LLM 结构化调用
```

也就是说，预算统计发生在 LLM 调用前。后续排查时，可以从提示词运行日志、上下文快照、上下文槽位日志中看到每个槽位的预算状态。

## 八、这一步达到了什么效果

现在 `content_draft_v2` 已经可以看到槽位级预算数据。

具体效果：

1. 能知道每个槽位的字符数和粗略 token 数。
2. 能知道每个槽位的预算上限。
3. 能知道哪个槽位超预算。
4. 能知道哪个槽位是必需的。
5. 能知道哪个槽位后续可以压缩或截断。
6. 能知道上下文里是否出现硬编码领域词。
7. 能通过已有 JSON 字段写入 PromptRunLog 和 ContextSnapshot，不需要新增数据库字段。

这为后续第 5.5.2 的压缩、Top-K 和第 5.6 的对比报告打基础。

## 九、这一步没有做什么

本次明确没有做：

- 没改 prompt 文案。
- 没调用真实 LLM。
- 没新增数据库字段。
- 没新增 migration。
- 没实现压缩。
- 没实现 Top-K。
- 没替换硬编码领域词。
- 没实现 `domain_profile` 自动生成。
- 没改前端。
- 没重构多 Agent。
- 没大改旧 `content_draft` / `review_report` 链路。

## 十、测试命令和测试结果

### 1. 预算工具测试

命令：

```bash
python -m pytest backend/tests/test_context_budget.py -q -s -p no:cacheprovider
```

结果：

```text
5 passed in 0.08s
```

### 2. Context Engineering 测试

命令：

```bash
python -m pytest backend/tests/test_context_engineering.py -q -s -p no:cacheprovider
```

结果：

```text
5 passed in 0.36s
```

### 3. content_draft_v2 集成测试

命令：

```bash
python -m pytest backend/tests/test_content_draft_v2.py -q -s -p no:cacheprovider
```

结果：未进入业务断言，测试收集阶段失败。

失败原因：

```text
ModuleNotFoundError: No module named 'psycopg2'
```

说明：当前本地 Python 环境缺少 PostgreSQL 驱动 `psycopg2`，导入 `app.core.database` 时失败。这不是本次预算字段代码导致的业务失败。

### 4. 全量测试

命令：

```bash
python -m pytest backend/tests -q -x -p no:cacheprovider
```

结果：测试收集阶段失败。

失败原因同样是：

```text
ModuleNotFoundError: No module named 'psycopg2'
```

### 5. 语法检查

命令：

```bash
python -m py_compile backend/app/context/context_budget.py backend/app/context/context_slots.py backend/app/context/context_builder.py backend/app/context/context_usage_logger.py backend/app/services/content_draft_v2_sev.py backend/tests/test_context_budget.py backend/tests/test_context_engineering.py backend/tests/test_content_draft_v2.py
```

结果：通过，无语法错误。

## 十一、下一步建议

下一步可以做第 5.5.2，但不要一次性全链路重构。

建议顺序：

1. 先基于本次 `budget_meta.over_budget` 找出最容易超预算的 slot。
2. 对 `COMPETITOR_EVIDENCE` 设计 Top-K 策略。
3. 对 `COMMENT_INSIGHT` 设计摘要压缩策略。
4. 对 `STRATEGY_MEMORY` 设计按新鲜度、置信度、同领域匹配的筛选策略。
5. 等 `content_draft_v2` 稳定后，再考虑接入 `review_report`。
6. 最后再逐步处理旧版 `content_draft`。

本次第 5.5.1 的重点是“先看得见”，不是“马上压缩”。现在系统已经能记录 slot 级预算数据，后续才有依据判断该压缩谁、保留谁、Top-K 谁。
