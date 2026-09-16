# Real XHS Collection Manual Acceptance

This sprint uses an external read-only collector adapter. The main product path must not use mock data as a substitute for real XHS collection.

## Provider

Current adapter: `XiaohongshuMcpProvider`

Expected runtime config:

```bash
XHS_MCP_BASE_URL=http://127.0.0.1:PORT
XHS_MCP_TIMEOUT_SECONDS=30
```

The external xiaohongshu-mcp service must expose read-only note and creator endpoints and return JSON. The project does not save XHS passwords, does not persist raw cookies, and does not bypass captcha.

## Acceptance Steps

1. Start the external xiaohongshu-mcp service outside this repository.
2. Complete the collector's normal login/session setup if it requires QR login or browser session.
3. Start this project backend and frontend.
4. In Agent Chat, send a request such as:

```json
{
  "account_id": 1,
  "text": "分析这些小红书笔记和同行账号，看看他们的人设、内容方向、用户在评论区关心什么",
  "attachments": {
    "note_urls": [
      "https://www.xiaohongshu.com/explore/..."
    ],
    "competitor_account_ids": [
      "xxxxx"
    ]
  }
}
```

5. The backend endpoint is `POST /agent/chat/execute-workflow`.
6. Open the workflow timeline in the response metadata:
   - `metadata.workflow_timeline[].action`
   - `metadata.workflow_timeline[].status`
   - `metadata.workflow_timeline[].data_count`
   - `metadata.workflow_timeline[].evidence_ids`
   - `metadata.workflow_timeline[].error_code`
   - `metadata.workflow_timeline[].error_message`
7. Verify that collected records are written to existing tables:
   - `competitor_account`
   - `competitor_note`
   - `xhs_note_snapshot`
   - `competitor_comment`
8. Verify `is_mock=false` and `source_type=XHS_MCP`.
9. Verify `ANALYZE_COMPETITOR_DATA` generates a `CompetitorAnalysisReport` only after collection steps succeed.

## Current Local Blocker

On this machine, `MediaCrawler`, `xiaohongshu-mcp`, `RapidOCR`, and `PaddleOCR` were not found in PATH or pip. Attempting to clone `NanmiCoder/MediaCrawler` failed with a network reset.

Because of that, automated tests use `FakeXhsProvider` only under `backend/tests/`. This is not a production fallback and is not evidence that real XHS collection has passed manual acceptance.
