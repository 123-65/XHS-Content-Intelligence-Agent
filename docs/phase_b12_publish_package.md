# Phase B12 - Publish Package V0

## Scope

B12 turns a final local draft into a manual publish package for XHS preparation.

It does not publish, log in to XHS, use cookies, create comments, call an LLM, regenerate evidence, create experiments, or update strategy memory.

The package is a preparation artifact only. Users still copy the text, download the images, open XHS themselves, upload manually, and later record the published note URL and metrics through the post-publish flow.

## Why There Is No Auto Publish

XHS publishing requires platform session state, account login, and user-side compliance decisions that should not be automated in this system. B12 therefore avoids:

- XHS network access.
- Cookie or session storage.
- Browser login handling.
- Automated upload or submit actions.
- Automated comments or engagement behavior.

This keeps B12 deterministic, testable, and clearly separated from post-publish tracking.

## API

### Create

`POST /agent/drafts/{draft_id}/publish-packages`

Request:

```json
{
  "account_id": 1,
  "confirmed": true,
  "review_report_id": 10,
  "style": "clean_knowledge_card",
  "card_count": 5
}
```

If `confirmed` is false, the service returns `WAITING_CONFIRMATION` and creates no row.

### List

`GET /agent/drafts/{draft_id}/publish-packages`

Returns packages for the draft, newest first.

### Detail

`GET /agent/publish-packages/{package_id}`

Returns the persisted package.

## Response Contents

The package contains:

- Copyable title, body, tags, and CTA.
- A cover card and image-card data for frontend Canvas PNG downloads.
- A manual publish checklist.
- Manual publish steps.
- Warnings when the package has no review report or the linked review report is high risk / not passed.
- Stats proving local preparation only: `llm_called=false`, `auto_publish=false`, `template_generation=frontend_canvas`.

The title, body, tags, and CTA are read from the final `ContentDraft`. For revised drafts, the service reads the B11 revised draft fields and records `source_type=REVISED_DRAFT` plus the `revision_plan_id` from `generation_context`.

## Image Generation

B12 does not use image-generation models. It stores structured `cover_card` and `image_cards` JSON, then Agent Workbench renders simple 1080x1440 knowledge-card PNGs in the browser with Canvas.

This avoids model cost, unstable visual output, Chinese text rendering errors from generated images, and backend binary generation complexity.

## PublishedNote Boundary

B12 never creates `PublishedNote`. That table remains reserved for the user after manual publishing, when the published URL and metrics can be recorded through the post-publish workflow.

## Status Rules

- `WAITING_CONFIRMATION`: request did not confirm generation.
- `DATA_INSUFFICIENT`: draft title or body is empty; no package is persisted.
- `READY`: package is created and no warning is present.
- `NEEDS_REVIEW`: package is created, but a missing or risky review report requires manual review.

## Frontend

Agent Workbench now shows `Publish Package V0` after a draft exists. It can create a local package, copy fields, preview image cards, and download PNG cards generated in the browser via Canvas.

If the final draft is still the B8 generated draft, the frontend sends the B9 `review_report_id`. If the final draft is a B11 revised draft, the frontend does not reuse the original draft's report because the report belongs to the source draft; the backend then marks the package `NEEDS_REVIEW` with a manual review warning.

## Tests

Commands run:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m pytest tests/test_publish_package_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_draft_revision_apply_api.py tests/test_draft_revision_plan_api.py tests/test_draft_review_api.py tests/test_draft_generation_api.py tests/test_draft_context_preview_api.py tests/test_operation_experiment_api.py tests/test_operation_run_api.py tests/test_evidence_refresh_run_api.py tests/test_data_refresh_run_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_agent_chat_api.py tests/test_agent_conversation_api.py tests/test_agent_chat_readonly_execute_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec frontend npm run build
```

Results:

- B12 API: `10 passed`.
- B11-B3 regression: `87 passed`.
- Agent regression: `46 passed`.
- Frontend build: passed.

## Not Done In B12

- No auto publish.
- No XHS access.
- No cookie storage.
- No login/session handling.
- No auto comments.
- No LLM calls.
- No draft mutation.
- No evidence refresh.
- No operation rerun.
- No new `ContentExperiment` or `ContentOpportunity`.
- No `PublishedNote`.
- No `CandidateMemory` or `StrategyMemory`.

## B13 Plan

B13 can add a manual post-publish intake step that starts after the user publishes on XHS:

- Record published note URL and publish time.
- Link the URL to the draft and experiment via `PublishedNote`.
- Capture public metrics snapshots.
- Run post-publish review from stored metrics and optional user-provided notes.
- Keep the same boundary: no cookie storage, no platform login automation, and no automated engagement.
