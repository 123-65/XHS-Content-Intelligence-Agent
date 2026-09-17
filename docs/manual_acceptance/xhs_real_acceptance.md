# XHS Real Data Acceptance

## Sprint Status

`SPRINT_PARTIAL`

Reason: the collector is installed, logged in, running, and reachable from the Docker backend, but no private real note URL or competitor profile URL was supplied for collection and database verification.

## Collector

- Acceptance date: 2026-09-17
- Project release: `xpzouying/xiaohongshu-mcp v2.4.0`
- MCP binary: `xiaohongshu-mcp-windows-amd64.exe`
- Login binary: `xiaohongshu-login-windows-amd64.exe`
- Windows binaries downloaded: yes, under the Git-ignored `tools/xiaohongshu-mcp/` directory
- Login tool run: yes
- Login status: `SUCCESS` (username and session data are intentionally not recorded)
- MCP process started: yes
- Host MCP URL: `http://localhost:18060/mcp`
- Docker backend base URL: `http://host.docker.internal:18060`
- Docker Host header: `localhost:18060`
- Backend connection: `SUCCESS`, verified from inside the backend container
- Session owner: external xiaohongshu-mcp; the application database stores no password, raw cookie, or QR-code content

Start commands:

```powershell
.\tools\xiaohongshu-mcp\xiaohongshu-login-windows-amd64.exe
.\tools\xiaohongshu-mcp\xiaohongshu-mcp-windows-amd64.exe
```

## Actual MCP Tools

`tools/list` was executed against the running v2.4.0 service. Read-only tools relevant to this workflow:

- `check_login_status`
- `get_feed_detail`
- `user_profile`
- `search_feeds`
- `list_feeds`

Verified arguments:

- `get_feed_detail`: `feed_id`, `xsec_token`, optional comment-loading controls
- `user_profile`: `user_id`, `xsec_token`, optional `tab`

The official tools require `xsec_token`. A bare account ID cannot satisfy the real `user_profile` contract; acceptance should use a full profile URL containing a current token. Tokens are removed from normalized source URLs and are not shown in the workflow timeline.

## Real Note Test

- Input note URL count: 0
- `SUCCESS`: 0
- `PARTIAL_SUCCESS`: 0
- `FAILED`: 0
- Real fields verified: not run
- Missing provider fields: not determined
- Parse failures: not determined
- Real notes written: 0
- Real comments written: 0
- `is_mock=false`: implemented and covered by adapter tests; not yet verified against a user-supplied note

## Real Account Test

- Input account count: 0
- Collection success: not run
- Profile fields verified: not run
- Recent notes: not run
- Real accounts written: 0

## Database And Agent Workflow

- New tables: none
- Modified tables: none
- Reused tables: `CompetitorAccount`, `CompetitorNote`, `CompetitorComment`, `XhsNoteSnapshot`, `CompetitorAnalysisReport`
- Real database write result: not run because no private acceptance input was supplied
- Agent collection to analysis workflow: covered by automated Fake Provider regression; not claimed as real acceptance
- Timeline: provider/data source/counts/duration/created IDs/warnings/errors implemented; real execution not yet recorded
- CompetitorReport real input: repository excludes mock notes, accounts, and comments; no real report was generated in this acceptance run
- Formal workflow Mock fallback: none found; provider failures remain failures

## Tests

- Backend: `494 passed, 1 skipped`
- Real integration: skipped by default as designed; requires `RUN_REAL_XHS_INTEGRATION=1`, `XHS_TEST_NOTE_URL`, and `XHS_TEST_ACCOUNT_ID`
- Frontend type check: passed
- Frontend production build: passed in the project Docker frontend environment
- Docker Compose configuration: valid

## Remaining Acceptance Steps

1. Supply one or more real note URLs containing a current `xsec_token` and one real profile URL containing a current `xsec_token` through private environment variables.
2. Run `backend/tests/integration/test_xhs_mcp_real.py` with `RUN_REAL_XHS_INTEGRATION=1`.
3. Run the Agent workflow and verify real rows, `is_mock=false`, timeline counts, and report evidence IDs in the existing database.
