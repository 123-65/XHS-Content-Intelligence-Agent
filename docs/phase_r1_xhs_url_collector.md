# R1 XHS URL Collector V0

## Why R1 Pauses Demo Work

B1-B15 already close the post-processing loop, but the project still needs a real data entry point. R1 therefore pauses demo seed work and adds a public XHS URL collection path.

This is not demo data and not mock replacement.

## User Input

The user only needs:

- `account_id`
- one or more XHS note URLs
- whether to collect top comments
- maximum comment count

## What The System Collects

The collector attempts to read public page data:

- source URL
- note id
- title
- content
- author name
- author profile URL
- publish time when available
- like count
- collect count
- comment count
- share count when available
- cover URL
- image URLs
- tags
- top comments
- raw provider parse evidence

Missing fields stay null or empty. R1 does not invent values.

## Storage

R1 writes successful or partially successful parsed results into existing tables:

- `CompetitorAccount`
- `CompetitorNote`
- `CompetitorComment`
- `XhsNoteSnapshot`
- `CrawlTask` as the collection run record

All collected business rows use:

- `source_type=URL_COLLECT`
- `is_mock=false` where the table has `is_mock`
- provider metadata in `raw_snapshot`

`XhsNoteSnapshot` already has image URL and metric fields. Because it does not currently have a `raw_snapshot` JSON field, raw provider detail is preserved in `CompetitorNote.raw_snapshot`, `CompetitorAccount.raw_snapshot`, and `CompetitorComment.raw_snapshot`; `XhsNoteSnapshot.raw_hash` stores a content hash.

## API

- `POST /agent/xhs/url-collect`
- `GET /agent/xhs/url-collect/runs?account_id=1`
- `GET /agent/xhs/url-collect/runs/{run_id}`

The create endpoint returns:

- `COMPLETED`
- `PARTIAL_SUCCESS`
- `FAILED`
- `WAITING_CONFIRMATION`

Each URL result keeps its provider status:

- `SUCCESS`
- `PARTIAL_SUCCESS`
- `COLLECT_FAILED`
- `LOGIN_REQUIRED`
- `CAPTCHA_REQUIRED`
- `RATE_LIMITED`
- `UNSUPPORTED_URL`
- `PARSE_FAILED`

## Provider

R1 adds a pluggable provider interface:

- `backend/app/collectors/xhs/base.py`
- `backend/app/collectors/xhs/simple_http_provider.py`

`SimpleHttpXhsProvider` uses public HTTP only. It parses actual HTML, meta tags, and script JSON if present.

It does not:

- save cookies;
- ask for cookies;
- log in;
- bypass captchas;
- high-frequency batch crawl;
- call LLM to fill missing fields;
- treat failures as success.

If a page needs login, captcha, JS rendering, or cannot be parsed reliably, R1 returns the explicit failure status.

Future Playwright, browser plugin, or MCP providers can implement the same provider contract.

## B4 Evidence Refresh

B4 reads `CompetitorNote` and `CompetitorComment` where `is_mock=false`.

R1 writes URL-collected notes and comments as `is_mock=false`, so B4 can use them directly. The R1 test suite verifies:

```text
R1 collect success
-> writes note/comment
-> B4 Evidence Refresh
-> not ONLY_MOCK_COMPETITOR_NOTES
```

## Not Done In R1

R1 does not:

- generate demo seed;
- generate fake title/content/comments/metrics;
- use mock data as real data;
- call LLM;
- save cookies;
- bypass captcha;
- write StrategyMemory;
- regenerate drafts;
- publish;
- comment.

## Verification

```bash
docker compose exec backend python -m pytest tests/test_xhs_url_collect_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_strategy_memory_confirmation_api.py tests/test_post_publish_review_api.py tests/test_manual_publish_backfill_api.py tests/test_publish_package_api.py tests/test_draft_revision_apply_api.py tests/test_draft_revision_plan_api.py tests/test_draft_review_api.py tests/test_draft_generation_api.py tests/test_draft_context_preview_api.py tests/test_operation_experiment_api.py tests/test_operation_run_api.py tests/test_evidence_refresh_run_api.py tests/test_data_refresh_run_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_agent_chat_api.py tests/test_agent_conversation_api.py tests/test_agent_chat_readonly_execute_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec frontend npm run build
```

## Current Limits

Simple HTTP may not collect complete data from JS-rendered or login-gated XHS pages. That is expected. The correct behavior is explicit failure or partial success, not fabricated data.
