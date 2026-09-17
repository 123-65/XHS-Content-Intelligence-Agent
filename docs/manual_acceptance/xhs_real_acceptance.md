# XHS Real Data Acceptance

## Acceptance Result

- Acceptance date: 2026-09-17
- `REAL_COLLECTION_ACCEPTANCE = PARTIAL`
- `AGENT_WORKFLOW_ACCEPTANCE = PASS`
- `COMPETITOR_ANALYSIS_QUALITY = NOT_EVALUATED_YET`

Collection is partial because the provider exposed only 10 of 124 comments for Note 1 and 10 of 86 comments for Note 2, and OCR is not configured. The Agent workflow itself passed: one natural-language request automatically executed all three planned tools and generated report `1829` without an intermediate user action.

## Collector

- Collector: `xpzouying/xiaohongshu-mcp v2.4.0`
- Login: `SUCCESS`
- Host MCP: `http://localhost:18060/mcp`
- Docker backend MCP: `http://host.docker.internal:18060/mcp`
- Backend connection: `SUCCESS`
- Required tools verified: `check_login_status`, `tools/list`, `get_feed_detail`, `user_profile`
- Formal provider: `xiaohongshu_mcp`
- Formal source type: `XHS_MCP`
- Mock fallback: none

No username, cookie, session value, complete URL, or query token is recorded in this document.

## Real Inputs

- Notes: 2
- Competitor accounts: 1
- Note 1 ID suffix: `6ff4`
- Note 2 ID suffix: `3457`
- Profile ID suffix: `7e7a`

## Note 1

- Title: `5分钟教会你，什么是agent？`
- Content: available
- Author: `开聊pro`; author ID and profile were available
- Publish time: available
- Likes: 3651
- Collects: 2478
- Total comment count: 124
- Comments received: 10
- Comments saved: 10
- Images: 1
- Cover: available
- Share count: missing from provider
- Tags: missing as a structured provider field
- Database IDs: competitor note `6483`, note snapshot `552`
- Status: `PARTIAL_SUCCESS`
- Warnings: `COMMENTS_PARTIAL_FROM_PROVIDER`, `OCR_OCR_PROVIDER_NOT_CONFIGURED`

## Note 2

- Title: `分享我三个月转agent的学习过程`
- Content: available
- Author: `美少女壮士`; author ID and profile were available
- Publish time: available
- Likes: 572
- Collects: 874
- Total comment count: 86
- Comments received: 10
- Comments saved: 10
- Images: 7
- Cover: available
- Share count: missing from provider
- Tags: missing as a structured provider field
- Database IDs: competitor note `6484`, note snapshot `553`
- Status: `PARTIAL_SUCCESS`
- Warnings: `COMMENTS_PARTIAL_FROM_PROVIDER`, `OCR_OCR_PROVIDER_NOT_CONFIGURED`

## Competitor Account

- Nickname: `FDE 现场手册`
- Bio: available; describes FDE research, enterprise AI implementation, delivery methods, and cases
- Avatar: available
- Followers: 12148
- Following: 155
- Liked/collected interactions: 156798
- Recent notes received and saved: 10
- Competitor account database ID: `1699`
- Status: `SUCCESS`

## Database Verification

The final isolated run used `account_id=2`, which had zero real competitor rows before execution.

- Real competitor accounts after run: 3, comprising two note authors and the supplied competitor account
- Real competitor notes after run: 12, comprising two supplied notes and ten recent profile notes
- Real comments after run: 20
- XHS note snapshots after run: 12
- All inspected rows: `is_mock=false`
- All inspected rows: provider `xiaohongshu_mcp`, source type `XHS_MCP`
- Forbidden source markers (`MockProvider`, `MANUAL_DEMO`, `FAKE`, `TEST`): none
- Raw snapshot token/cookie/session/authorization leakage: none found
- New tables or migrations: none

## Agent Workflow

User message:

`分析我提供的这两篇 Agent 相关小红书笔记和这个同行账号，告诉我这个同行账号的人设、主要内容方向、这些内容为什么有人关注，以及评论区用户主要关心什么。`

- Router intent: `ANALYZE_COMPETITOR`
- Planner actions: `COLLECT_XHS_NOTES`, `COLLECT_XHS_ACCOUNTS`, `ANALYZE_COMPETITOR_DATA`
- Executor order: identical to the Planner order
- Intermediate manual action: none
- Current State/business artifact: account `2`, report `1829`
- Report engine: `SEMANTIC_RULE_BASELINE`
- Report provider/data source: `XHS_MCP` / `REAL`
- Report ID: `1829`
- Used competitor account IDs: `1699`, `1698`, `1697`
- Used competitor note IDs: `6483`, `6484`, `6485` through `6494`
- Used comment IDs: `6553` through `6572`
- Mock rows in report evidence: none

## Timeline

1. `COLLECT_XHS_NOTES`: 22,733 ms; 2 notes, 20 comments received, 20 comments saved, 8 images; provider `XHS_MCP`, data source `REAL`.
2. `COLLECT_XHS_ACCOUNTS`: 9,028 ms; 1 account and 10 recent notes saved; provider `XHS_MCP`, data source `REAL`.
3. `ANALYZE_COMPETITOR_DATA`: 37 ms; 12 notes and 20 comments analyzed; report `1829`; engine `SEMANTIC_RULE_BASELINE`.

Created IDs, counts, durations, provider, data source, warnings, and errors were present in the API Timeline payload and are rendered by the existing Agent Workbench Timeline bindings.

## Semantic Rule Baseline

Observed output:

- Persona summary: `知识分享号` (3 accounts)
- Main content pillar: `综合内容` (10 notes)
- Other pillars: `避坑复盘`, `学习路线`, `项目实战`, `求职简历`
- Comment demands: `UNKNOWN` 19, `ANXIETY` 1
- Viral analysis correctly ranked Note 1 above Note 2 using real engagement metrics
- Opportunities were generated from the detected pillars and demand labels

Clearly accurate:

- The two supplied note titles, authors, engagement counts, images, and comments are real provider evidence.
- Note 1 was correctly identified as the stronger engagement sample.
- FDE recent-note titles were included as real account evidence.

Clearly rigid or incorrect:

- `知识分享号` misses the supplied FDE account's enterprise AI implementation and delivery positioning.
- `综合内容` is too generic to describe the observed FDE themes.
- 19 of 20 comments were classified as `UNKNOWN`, so the main user concerns were not meaningfully extracted.
- Opportunity text such as `综合内容 × UNKNOWN` is mechanically correct but not decision-useful.

Real data not effectively used:

- The account bio, follower/following counts, and aggregate interactions did not materially shape persona output.
- Image content was not used because OCR is not configured.
- Comment semantics beyond the fixed keyword rules were mostly unused.
- Missing share counts and structured tags were not inferred or replaced.

These observations are the baseline for a future rule-based versus LLM structured-analysis comparison. They do not claim that analysis quality is good.

## Tests

- Existing backend suite: `499 passed, 1 skipped`
- Default skip: the private real integration test remains opt-in by design
- Real integration with `RUN_REAL_XHS_INTEGRATION=1`: `1 passed`
- Frontend: `vue-tsc --noEmit` passed; Vite production build passed
- Frontend and backend HTTP checks: `200`

## Final Status

- `REAL_COLLECTION_ACCEPTANCE = PARTIAL`
- `AGENT_WORKFLOW_ACCEPTANCE = PASS`
- `COMPETITOR_ANALYSIS_QUALITY = NOT_EVALUATED_YET`

The system now has sufficient real-data collection, persistence, evidence, and Agent workflow conditions to begin analysis-quality optimization on real data.
