# Phase 2.7B E2E-012 Frontend Route / Lazy Load Final Report

Date: 2026-09-27

## 1. Route Inventory

| Path | Page | Loading | Purpose |
| --- | --- | --- | --- |
| `/` | redirect | eager redirect | Agent entry |
| `/agent/workbench` | redirect | eager redirect | Legacy-compatible Agent entry |
| `/agent/chat/:conversationId?` | `AgentChatView` | lazy import | Conversation / Agent |
| `/agent/research/:artifactRef` | `ResearchDetailView` | lazy import | Research detail |
| `/agent/strategy/:artifactRef` | `StrategyDetailView` | lazy import | Strategy detail |
| `/agent/draft/:draftRef` | `DraftDetailView` | lazy import | Draft/version/manual publish |
| `/agent/publication/:publishedNoteRef` | `PublicationDetailView` | lazy import | PublishedNote metrics/review |
| `/agent/runs/:runRef` | `RunDetailView` | lazy import | Workflow run detail |
| `/developer/agent-trace` | `DeveloperAgentTrace` | lazy import | Developer diagnostics |

There is no dedicated Review route. The intended product surface embeds review data in Publication detail.

## 2. Lazy Route Design

All page routes use Vue Router dynamic imports. Production build emitted separate JS chunks for Agent Chat, Research, Strategy, Draft, Publication, Run, and Developer Trace. Route lazy loading is PASS.

## 3. Product Page Structure

The application uses a small Agent Chat entry plus route-owned detail views. It does not put Research, Strategy, Draft, Publish, Metrics, Review, and Memory into one stateful giant workbench. Structure is PASS.

## 4. Canonical API Usage

- Natural-language entry: `POST /api/agent/turns`.
- Detail reads: canonical Research, Strategy, Draft, Publication, and Run endpoints.
- Manual publish: `POST /api/publish-packages` and `POST /api/published-notes`.
- Private metrics backend endpoint exists, but the frontend API module and UI do not expose it.
- No production frontend call to repository, internal Workflow, or test-only endpoint was found.

## 5. Agent Frontend Boundary

The frontend submits conversation, text, account, workspace selection, materials, and `client_request_id`. It does not submit internal intent, workflow name, tool name, workflow step, checkpoint FSM, or planner result. PASS.

## 6. Browser Startup

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Edge headless controlled-browser run rendered the real Vue SPA and Draft detail shell.
- Direct HTTP checks for `/`, `/agent/draft/2625`, and `/agent/publication/592` returned the SPA shell with HTTP 200.

## 7. Core Page Smoke

The application and Draft route render without a blank-page or route-level 404. The controlled-browser Draft 2625 run rendered `DRAFT ... #2625`, then displayed `请先选择账号`. Therefore browser startup passes, but the core detail flow does not.

Additional headless runs were stopped after Edge failed to exit reliably; they were not counted as product failures or passes. Static route/API evidence was used only for RCA, not as a substitute for an E2E PASS.

## 8. Draft Version UI

The Draft page contains a version selector, selected-version title/body/tags preview, and initializes to the latest version. Its data contract can represent V1-V4. However, direct access cannot load the canonical Draft because account context exists only in the in-memory store. FAIL as a usable product entry.

## 9. Manual Publish UI

Implementation is contract-correct once the page has account context:

- User selects an exact version.
- Preview reads the selected immutable snapshot.
- Package request submits `account_id + draft_version_id`.
- Registration submits `publish_package_ref`; it does not reselect a version.
- UI explicitly instructs manual XHS publishing and does not automate posting.

The feature is present, but direct/refresh usability remains blocked by DEFECT-021.

## 10. Private Metrics UI

Publication detail can read and display private metrics, including null as `未提供`. It provides no form/action for `POST /api/published-notes/{ref}/private-metrics`; `unifiedAgent.ts` also has no corresponding write call. Required fields cannot be entered through the product UI. FAIL: DEFECT-022.

## 11. Published Version Display

Publication detail displays the exact `published_draft_version` and would show V2 for PublishedNote 592. Draft detail displays version history and marks latest V4. Neither surface provides the required usable V2-published versus V4-latest distinction, and both are independently blocked on direct access by missing account context. FAIL: DEFECT-024. No evidence suggests the backend lineage changed; E2E-011 remains frozen.

## 12. Review UI

Publication detail embeds the canonical post-publish review and strategy candidates. However, the Agent artifact-card router maps a `POST_PUBLISH_REVIEW` or `STRATEGY_CANDIDATE` artifact ID directly to `/agent/publication/{artifact.id}`. Review 2144 is not PublishedNote 2144; its canonical parent is PublishedNote 592. The formal card entry therefore addresses the wrong resource. FAIL: DEFECT-023.

## 13. Lazy Data Loading

Architecture tests confirm Chat does not fetch artifact details and each detail view owns an independent on-mount fetch/abort boundary. No eager all-Draft/all-PublishedNote/all-Review/all-metrics fetch was found. PASS.

## 14. Build / Route Chunk Evidence

`npm run build` PASS: 3263 modules transformed. Separate route assets include `AgentChatView`, `ResearchDetailView`, `StrategyDetailView`, `DraftDetailView`, `PublicationDetailView`, `RunDetailView`, and `DeveloperAgentTrace`. The existing main-chunk size warning is not expanded into a performance task in this acceptance.

## 15. Mock / Fake Success Check

No mock provider, hardcoded success, fake metric, fake Draft, or fake Review source was found in the production core pages. `is_mock` appears only as diagnostic data in Developer Trace. PASS.

## 16. Browser Console / API Errors

The successful Draft browser capture had no route crash or blank page. Chromium sync/task-manager network warnings were environment noise, not application API evidence. The visible account-selection error is a handled UI error and the symptom of DEFECT-021. No unsupported claim of a clean full browser console is made.

## 17. Direct Route / Refresh

FAIL. The account is held only in non-persisted Pinia memory. Every detail view stops before its canonical request when `store.account_ref` is absent. A real browser direct visit to `/agent/draft/2625` reproduced this exact condition. Refresh/direct link cannot recover account identity from route, persisted product state, or a product selection flow.

## 18. Product Defect

- `DEFECT-021 = CONFIRMED / RCA COMPLETE / NOT FIXED`: detail routes depend on volatile in-memory `account_ref`; direct route/refresh cannot load.
- `DEFECT-022 = CONFIRMED / RCA COMPLETE / NOT FIXED`: Private Metrics has read display but no production write entry.
- `DEFECT-023 = CONFIRMED / RCA COMPLETE / NOT FIXED`: Review/Candidate artifact IDs are routed as PublishedNote IDs.
- `DEFECT-024 = CONFIRMED / RCA COMPLETE / NOT FIXED`: product UI does not provide a usable canonical distinction between published V2 and latest V4.

No broad frontend architecture change was attempted.

## 19. Regression

- Frontend tests: 7/7 PASS.
- Typecheck + production build: PASS.
- `git diff --check`: exit 0; only existing LF-to-CRLF warnings.
- Alembic: `d8e9f0a1b2c3 (head)`.
- Migration: 0.
- Backend full suite was not rerun because no implementation changed.

## 20. E2E-012 Final Status

`E2E-012 = BLOCKED / FRONTEND PRODUCT ENTRY AND DIRECT-ROUTE DEFECTS`

Route architecture, lazy loading, canonical API boundaries, and manual-publish request semantics pass. The acceptance as a whole cannot pass while DEFECT-021 through DEFECT-024 remain open.

## 21. Phase 2.7B Final Status

`Phase 2.7B = INCOMPLETE / BLOCKED BY E2E-012`

E2E-011 remains `PASS / FROZEN`. Phase 2.7B is not declared complete.

## 22. 面试资产

No success Q&A was added. Verified architecture evidence can later update the existing route-based/lazy-loading answer, but the current product-entry defects must not be presented as completed delivery.

## 23. 下一步

Fix the four narrowly identified product defects, run targeted frontend regressions, then rerun the controlled-browser E2E-012 acceptance. Do not start Testing Track before E2E-012 passes.

## 24. Git

No commit, add, reset, restore, clean, or stash was executed. The worktree already contained extensive Phase 2 changes; this acceptance added only this report and the corresponding status note.
