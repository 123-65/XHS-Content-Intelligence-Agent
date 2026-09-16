# B15 Strategy Memory Confirmation V0

## Goal

B15 turns B14 post-publish review candidates into confirmed `StrategyMemory` records only after user selection.

B14 produces `strategy_memory_candidates` from manual post-publish metrics. B15 reads the B14 `ReviewReport`, reconstructs the available candidates, lets the user select and edit them, and writes only selected candidates into `StrategyMemory`.

## Why Confirmation Is Required

Post-publish review is based on a single manual snapshot. It may be useful, but it is not automatically trusted as long-term strategy.

B15 therefore does not run automatic memory extraction. It keeps the user in control:

- unselected candidates are ignored;
- edited candidate content is saved as the memory text;
- `confirmed=false` never writes memory;
- repeated confirmation skips duplicates instead of creating repeated memories.

## API

- `GET /agent/post-publish-reviews/{review_id}/strategy-memory-candidates`
- `POST /agent/post-publish-reviews/{review_id}/strategy-memories/confirm`
- `GET /agent/accounts/{account_id}/strategy-memories`

The confirm request accepts:

- `account_id`
- `confirmed`
- `selected_candidates`
- optional `conversation_id`

## StrategyMemory Storage

B15 reuses the existing `strategy_memory` table. No new table was added.

The existing columns store:

- `account_id`
- `memory_type`
- `summary`
- `pattern`
- `confidence`
- `source_review_report_id`
- `status=VALIDATED`

Additional provenance is stored in `metadata_payload`:

```json
{
  "source_type": "POST_PUBLISH_REVIEW_V0",
  "source_review_id": 1,
  "source_published_note_id": 1,
  "source_metric_snapshot_id": 1,
  "source_package_id": 1,
  "source_candidate_index": 0
}
```

Supporting evidence is written to `memory_evidence`.

## Deduplication

V0 deduplicates in the service layer by:

```text
account_id + source_review_report_id + source_candidate_index
```

Duplicate confirmation returns `skipped_duplicates` and does not create another memory.

## CurrentState

If `conversation_id` is provided:

- when new memory is created, `current_target_type=STRATEGY_MEMORY`, `current_target_id=<last created memory id>`, `last_action=CONFIRM_STRATEGY_MEMORY`;
- when all selected candidates are duplicates, `last_action=CONFIRM_STRATEGY_MEMORY_SKIPPED`.

## B7 Read Path

B7 Draft Context Preview already reads `StrategyMemory` by `account_id` where status is `CANDIDATE` or `VALIDATED`.

B15 writes confirmed memories as `VALIDATED`, so the next B7 preview can include them in `context.strategy_memories`.

## Frontend

`AgentWorkbench` now shows `Strategy Memory Confirmation V0` after a B14 review exists.

The UI displays candidates with:

- checkbox selection;
- editable `memory_type`;
- editable `content`;
- editable `evidence`;
- editable `confidence`;
- confirmation result;
- created memory ids;
- skipped duplicates;
- current account StrategyMemory list.

Candidates are not selected by default.

## Not Done In B15

B15 does not:

- call LLM;
- access XHS;
- scrape metrics;
- auto publish;
- auto comment;
- regenerate draft;
- regenerate publish package;
- regenerate evidence;
- rerun operation analysis;
- regenerate post-publish review;
- call old `extract_memories`;
- write `CandidateMemory`;
- write unconfirmed candidates.

## Verification

Required commands:

```bash
docker compose exec backend python -m pytest tests/test_strategy_memory_confirmation_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_post_publish_review_api.py tests/test_manual_publish_backfill_api.py tests/test_publish_package_api.py tests/test_draft_revision_apply_api.py tests/test_draft_revision_plan_api.py tests/test_draft_review_api.py tests/test_draft_generation_api.py tests/test_draft_context_preview_api.py tests/test_operation_experiment_api.py tests/test_operation_run_api.py tests/test_evidence_refresh_run_api.py tests/test_data_refresh_run_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec backend python -m pytest tests/test_agent_chat_api.py tests/test_agent_conversation_api.py tests/test_agent_chat_readonly_execute_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
docker compose exec frontend npm run build
```

## Next Step

B16 can use confirmed StrategyMemory more visibly in operation planning, ranking, or draft-context explanations, while keeping the same human-controlled memory boundary.
