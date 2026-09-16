# Phase B13 - Manual Publish & Metrics Backfill V0

## Goal

B13 starts after B12. The user has manually downloaded cards, copied copy, opened XHS, and published the note themselves. B13 records the user's manually supplied publish URL and metrics so B14 can run post-publish review later.

## Why Manual Backfill

Publishing and metric collection require platform session state and user judgment. This system should not automate XHS login, store cookies, upload posts, scrape metrics, or perform engagement actions.

B13 is therefore a local recordkeeping step:

1. User manually publishes on XHS.
2. User copies the note URL and visible metrics.
3. System stores `PublishedNote`, `PublicMetricSnapshot`, and `PrivateConversionSnapshot`.

## Relationship To B12

B12 creates `PublishPackage`, which contains the final copy and renderable card data. B13 links the manual publish record back to that package using `PublishedNote.raw_snapshot.publish_package_id`.

The service reads:

- `PublishPackage`
- `ContentDraft`

It then uses the draft's `experiment_id` to create a `PublishedNote` without mutating the draft or experiment.

## Stored Data

B13 stores:

- `PublishedNote`: note URL, platform, publish time, draft/experiment linkage, package linkage in `raw_snapshot`.
- `PublicMetricSnapshot`: likes, collects, comments, shares, follower gain as `follow_count`, source marked `MANUAL`.
- `PrivateConversionSnapshot`: lead count and source marked `MANUAL`.

No new table is introduced.

## Metric Source

All B13 metrics are marked `source_type=MANUAL` because they come from the user's manual input. B13 does not use `use_mock`, seed data, crawler data, or provider data.

## Duplicate Backfill

The same `package_id` does not create multiple `PublishedNote` rows. If the package was already recorded, B13 reuses the existing `PublishedNote` and appends new metric/conversion snapshots. This supports later manual updates such as 1h, 24h, or 7d snapshots without duplicating the published note.

## API

### Record Manual Publish

`POST /agent/publish-packages/{package_id}/manual-publish`

```json
{
  "account_id": 1,
  "confirmed": true,
  "platform": "xhs",
  "note_url": "https://www.xiaohongshu.com/explore/...",
  "published_at": "2026-09-16T20:00:00",
  "title": "Optional title",
  "like_count": 0,
  "collect_count": 0,
  "comment_count": 0,
  "share_count": 0,
  "follower_gain": 0,
  "lead_count": 0,
  "remark": "Manual backfill note"
}
```

### List Published Notes

`GET /agent/published-notes?account_id=1&limit=20`

### Detail

`GET /agent/published-notes/{published_note_id}`

## Validation

- `confirmed=false` returns `WAITING_CONFIRMATION` and writes nothing.
- `account_id` must match the package.
- `note_url` is required.
- `note_url` must look like a XHS link, but the system does not request it.
- Metrics must be non-negative.
- The same package reuses the existing `PublishedNote`.

## Frontend

Agent Workbench shows `Manual Publish Backfill V0` after a publish package exists. The user can enter the XHS URL, publish time, title, metrics, and remark. The UI has no auto-publish, auto-scrape, or auto-comment button.

## Tests

Commands run:

```bash
docker compose exec backend python -m pytest tests/test_manual_publish_backfill_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_publish_package_api.py tests/test_draft_revision_apply_api.py tests/test_draft_revision_plan_api.py tests/test_draft_review_api.py tests/test_draft_generation_api.py tests/test_draft_context_preview_api.py tests/test_operation_experiment_api.py tests/test_operation_run_api.py tests/test_evidence_refresh_run_api.py tests/test_data_refresh_run_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_agent_chat_api.py tests/test_agent_conversation_api.py tests/test_agent_chat_readonly_execute_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec frontend npm run build
```

Result:

- B13 API: `10 passed`.
- B12-B3 regression: `97 passed`.
- Agent regression: `46 passed`.
- Frontend build: passed.

Full regression and frontend build are part of the B13 completion checklist.

## Not Done In B13

- No XHS access.
- No external link request.
- No cookie storage.
- No login/session handling.
- No auto metric scrape.
- No mock metrics as real results.
- No auto publish.
- No auto comment.
- No LLM calls.
- No draft regeneration or mutation.
- No publish package regeneration.
- No evidence refresh or operation rerun.
- No `CandidateMemory` or `StrategyMemory`.

## B14 Plan

B14 can use the recorded `PublishedNote` and metric snapshots to create a post-publish review:

- Compare metrics against experiment targets.
- Summarize public and private conversion signals.
- Produce factual review reports.
- Keep memory extraction as a separate explicit step after review, not inside B13.
