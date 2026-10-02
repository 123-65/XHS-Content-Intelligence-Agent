# Phase 2.7B LLM 解阻报告

## 一、现有 LLM Adapter

| Provider | Adapter | Model 配置字段 | Credential 配置字段 |
|---|---|---|---|
| Qwen | QwenProvider | LLM_MODEL | LLM_API_KEY |
| DeepSeek | DeepSeekProvider | LLM_MODEL | LLM_API_KEY |
| Zhipu | ZhipuProvider | LLM_MODEL | LLM_API_KEY |

三者都通过项目唯一 `LLMClient` 与 OpenAI-compatible 基类调用；未新增 Provider 或第二套 Client。

## 二、本地凭据状态

| Provider | Model | Endpoint / Credential | 是否可测试 |
|---|---|---|---|
| Qwen | qwen-plus | CONFIGURED / CONFIGURED | YES |
| DeepSeek | 未配置 | MISSING / MISSING | NO |
| Zhipu | 未配置 | MISSING / MISSING | NO |

根目录、backend `.env` 与 backend 容器生效配置一致。Secret 未输出。

## 三、真实 Smoke 结果

| Provider | Model | is_mock | Provider Result | Structured Output | Latency | Error Code |
|---|---|---:|---|---|---:|---|
| Qwen | qwen-plus | false | HTTP 403 | FAIL | 4545 ms | AccessDenied.Unpurchased |
| DeepSeek | - | - | NOT RUN / CREDENTIAL MISSING | NOT RUN | - | CONFIG_MISSING |
| Zhipu | - | - | NOT RUN / CREDENTIAL MISSING | NOT RUN | - | CONFIG_MISSING |

Smoke 统一经过 `LLMClient.generate_structured()`，使用最小 JSON Schema 与最小 prompt；未直接调用厂商 SDK。

## 四、最终可用 Provider / Model

无。当前本地配置中不存在同时满足 `available=true`、`is_mock=false`、structured output PASS 的模型。

Qwen 的配置 health 只能证明 key/base URL/model 字段完整；真实调用的 `AccessDenied.Unpurchased` 证明当前账号没有 `qwen-plus` 调用权限。

## 五、配置修改

未修改正式运行配置。没有可验证成功的替代配置，禁止盲切 DeepSeek/Zhipu 或其他 Qwen model。

## 六、Structured Smoke Result

`FAIL / MODEL_NOT_PURCHASED / MODEL_PERMISSION`。

## 七、Phase 2.7B 是否可以 Resume

不可以。保持 `Phase 2.7B BLOCKED / NOT ACCEPTED`。未执行 E2E-002，未重新执行 E2E-001。

## 八、下一步

用户需要执行以下任一外部操作：

1. 在当前阿里云 Model Studio workspace 为 `qwen-plus` 开通/购买调用权限；或
2. 在本地正式配置中提供现有 Adapter 已支持且账号实际可调用的 DeepSeek/Zhipu/Qwen 低成本模型配置。

完成后先重启 backend，并再次通过统一 `LLMClient.generate_structured()` 执行 smoke。只有 smoke PASS 后，下一步才是：

`Resume E2E-002 using Conversation 874 / Research Artifact 2862`。

不得重新执行 E2E-001。
