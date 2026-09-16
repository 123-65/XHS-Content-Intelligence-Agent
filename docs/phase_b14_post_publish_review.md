# B14 Post Publish Review V0

## Scope

B14 adds a controlled post-publish review step after manual publish backfill.

The review only reads local records:

- `PublishedNote`
- latest `PublicMetricSnapshot`
- latest `PrivateConversionSnapshot`
- `PublishPackage`
- `ContentDraft`
- `ContentExperiment`
- `ReviewReport`

It does not access XHS, scrape metrics, publish content, comment, call LLM, regenerate drafts, regenerate evidence, run operation analysis, or write `CandidateMemory` / `StrategyMemory`.

## API

- `POST /agent/published-notes/{published_note_id}/post-publish-reviews`
- `GET /agent/published-notes/{published_note_id}/post-publish-reviews`
- `GET /agent/post-publish-reviews/{review_id}`

The create endpoint requires `confirmed=true`. Without confirmation it returns `WAITING_CONFIRMATION` and does not create a `ReviewReport`.

## Review Rules

The service stores a `ReviewReport` with `review_type=POST_PUBLISH_REVIEW_V0`.

It calculates:

- `metric_summary`: views, likes, collects, comments, shares, follower gain, engagement count, collect-like ratio, comment-like ratio.
- `target_comparison`: compares the experiment target metric with manual snapshot values when target values are available.
- `conversion_summary`: lead count, follower gain, lead rate.
- `data_gaps`: missing comment detail, missing private conversion snapshot, unknown target, zero metrics, or mock metric source.
- `strategy_memory_candidates`: candidate-only conclusions for B15. They are returned in the API response and are not persisted as memory.

Zero engagement is treated as `UNKNOWN_TARGET` instead of a failure because the observation window may be too early.

## Frontend

`AgentWorkbench` now shows `Post Publish Review V0` after `Manual Publish Backfill V0` records a `published_note_id`.

The card displays summary, metrics, target comparison, conversion summary, insights, data gaps, next actions, and strategy memory candidates.

## Verification

Required commands:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m pytest tests/test_post_publish_review_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_manual_publish_backfill_api.py tests/test_publish_package_api.py tests/test_draft_revision_apply_api.py tests/test_draft_revision_plan_api.py tests/test_draft_review_api.py tests/test_draft_generation_api.py tests/test_draft_context_preview_api.py tests/test_operation_experiment_api.py tests/test_operation_run_api.py tests/test_evidence_refresh_run_api.py tests/test_data_refresh_run_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_agent_chat_api.py tests/test_agent_conversation_api.py tests/test_agent_chat_readonly_execute_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec frontend npm run build
```

## B15 Handoff

B15 can turn `strategy_memory_candidates` into an explicit confirmation flow. B14 deliberately stops before memory persistence.
