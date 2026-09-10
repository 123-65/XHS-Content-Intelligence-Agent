# XHS Growth Intelligence Agent 工程指标基线

## 1. 基线说明

本文档记录当前项目在 Agent Trace、Mock/Seed 治理、Provider 状态码、LLM 结构化输出等方面的工程化基线。

当前指标只记录已经完成且有测试支撑的内容。暂不填写 token 降低、延迟降低、成本下降等性能指标，因为 Context Engineering / Eval 尚未完成。

后续会在第 5 阶段和第 8 阶段补充 token、延迟、Schema 通过率、输出质量等量化数据。

## 2. 当前测试基线

- 全量测试：115 passed, 1 warning
- warning 来源：Starlette TestClient deprecation，不影响业务逻辑
- 覆盖模块：
  - Agent Runtime / Trace
  - Crawler Collection
  - LLM Client
  - Content Draft
  - Content Draft V2
  - Review Report
  - Post Publish 等已有测试

## 3. Mock / Seed 默认链路治理基线

已完成的默认链路治理：

- seed_sample 不再进入生产默认 Provider 顺序
- MockLLMProvider 不再作为真实 LLM 失败时的隐式 fallback
- MCPToolGateway 默认不返回 mock://web-search
- 旧 Crawler Factory 未知 provider 不再自动回退 Mock
- content_draft / review_report 默认 use_mock=False
- 竞品数据默认 source_type/provider_name 不再是 SEED_SAMPLE

当前可记录指标：

- 生产默认链路 Mock/Seed 自动启用风险：已隔离
- seed_sample 使用方式：仅显式 demo/test
- MockLLM 使用方式：仅显式 provider_name="mock"
- Mock MCP 使用方式：仅 allow_mock=True
- mock 草稿 / mock 审核使用方式：仅显式 use_mock=True

## 4. Agent Trace 可观测性基线

Trace 当前支持字段：

- workflow_name
- step_name
- tool_name
- status
- input_payload
- output_payload / output_summary
- error_code
- error_message
- fallback_used
- fallback_tool_name
- latency_ms / duration_ms
- mock_used / is_mock 相关识别字段

状态语义：

- SUCCESS：工具成功，并拿到有效业务结果
- FALLBACK_USED：原工具失败或缺少业务数据，但 fallback 返回结构化提示
- FAILED：工具失败，且无法恢复

## 5. Provider 状态码统一基线

已统一枚举：

- DataStatus
- ProviderSourceType
- ProviderErrorCode

覆盖范围：

- Crawler Provider
- MCP Gateway
- LLM Client / Router
- fallback_registry
- fallback policy
- provider health
- crawler_collection schema

关键错误码：

- MCP_NOT_CONFIGURED
- MANUAL_SNAPSHOT_REQUIRED
- COLLECTION_FAILED
- LLM_CONFIG_MISSING
- LLM_PROVIDER_UNAVAILABLE
- LLM_OUTPUT_PARSE_FAILED
- LLM_SCHEMA_INVALID
- MCP_CALL_FAILED

## 6. LLM 结构化输出基线

已覆盖能力：

- LLMClient 统一处理 Pydantic 实例 / dict / JSON string
- 非法 JSON 抛 LLM_OUTPUT_PARSE_FAILED
- JSON 非对象抛 LLM_OUTPUT_PARSE_FAILED
- Schema 不合法抛 LLM_SCHEMA_INVALID
- 不 fallback mock
- 不允许空 dict / 脏 JSON 伪装成功

测试覆盖：

- 合法 JSON 字符串解析成功
- 非法 JSON 失败
- JSON array 失败
- Schema 不合法失败
- 显式 mock structured 仍通过

## 7. 草稿生成与审核报告基线

草稿生成：

- 默认 use_mock=False
- 默认走真实 LLMClient structured 输出
- LLM 成功后才入库
- LLM_CONFIG_MISSING / LLM_OUTPUT_PARSE_FAILED / LLM_SCHEMA_INVALID 时不创建草稿

审核报告：

- 默认 use_mock=False
- 默认走真实 LLMClient structured 输出
- LLM 成功后才创建审核报告
- LLM_CONFIG_MISSING / LLM_OUTPUT_PARSE_FAILED / LLM_SCHEMA_INVALID 时不创建审核报告

## 8. 当前可以写进简历的表达

1. 实现 Agent Trace 可观测机制，记录 workflow、step、tool、fallback、error_code、latency_ms 等执行字段，支持定位 Agent 执行失败、数据缺失和 fallback 原因。

2. 治理 Agent 生产链路中的 Mock / Seed 数据污染问题，将 seed_sample、MockLLMProvider、Mock MCP Gateway、旧 Crawler Mock Provider 从默认链路隔离，仅允许测试/演示显式启用。

3. 统一 Provider 状态码体系，抽象 DataStatus、ProviderSourceType、ProviderErrorCode，并覆盖 Crawler、MCP、LLM、fallback policy、provider health 等模块；通过回归测试保障状态语义稳定。

4. 在 LLMClient 层实现结构化输出强校验，统一处理 JSON 解析失败和 Schema 校验失败，避免脏数据进入草稿生成和审核报告链路。

## 9. 后续待补充量化指标

第 5 阶段 Context Engineering 后补：

- 平均输入 token
- 压缩前后 token 对比
- 单次调用成本估算
- 上下文构建耗时
- 超长上下文失败率

第 8 阶段 Eval / Regression 后补：

- Schema 通过率
- 输出解析成功率
- 回归测试通过率
- 内容机会命中率
- 人工评分
- 失败样本分布

第 9 / 前端看板后补：

- Trace 查询效率
- 错误定位耗时
- 数据来源可视化覆盖率
