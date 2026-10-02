# Phase 2.7B DEFECT-021 Report

Date: 2026-09-27

## Scope

Only `DEFECT-021 = DETAIL ROUTE CANNOT RESTORE ACCOUNT CONTEXT` was addressed. DEFECT-022/023/024 and Testing Track were not started.

## RCA

The explicitly selected account existed only in volatile Pinia state. A full SPA refresh rebuilt the store with `account_ref=null`, so every detail view stopped before its canonical API request and displayed `请先选择账号`.

The project uses Pinia but has no persistence plugin or existing state persistence package.

## Minimal implementation

- Persist only the explicitly selected positive integer Account ID under `xhs-growth:selected-account-ref`.
- Hydrate `account_ref` synchronously when the Pinia store is created.
- Update or remove the persisted value through the existing `switchAccount` action.
- Reject and clear malformed, non-integer, zero, and negative stored values.
- Clear a restored selection after a canonical detail API returns HTTP 403/404; do not switch to another account automatically.
- Validate a restored selection against the canonical account list when Agent Chat opens.
- Continue sending `account_ref` to canonical APIs. Backend ownership validation remains the authorization boundary.
- Do not infer an account from Draft, Artifact, recent objects, or hard-coded Account 8456.

No AccountContextManager, session framework, backend preference, migration, or new dependency was added.

## Tests

Targeted cases cover:

1. Account 8456 is persisted.
2. A reconstructed state source restores 8456.
3. Switching Account replaces the persisted value.
4. Invalid values are cleared without crashing.
5. No prior selection remains unselected.
6. 403/404 invalidates context while unrelated errors do not.
7. Agent request contract gains no workflow/tool/checkpoint/planner/intent field.

Results:

- Frontend: 13/13 PASS.
- Typecheck + production build: PASS.
- `git diff --check`: PASS, with pre-existing LF/CRLF warnings only.
- Alembic: `d8e9f0a1b2c3 (head)`.
- Migration: 0.
- Backend code changed: no.

## Real browser attempt

The formal frontend and backend were running. Multiple isolated Edge profiles were attempted through native headless mode and DevTools using PowerShell and Python clients. Edge created the DevTools endpoint, but the renderer/target either reset the WebSocket or reported `Target crashed`. The environment has no Selenium or EdgeDriver, and no browser framework or driver was installed.

Because the required real sequence—select Account 8456, load Draft 2625, refresh, and direct-navigate in the same browser context—did not produce complete observable evidence, the closing condition is not met.

## Status

- `DEFECT-021 = IMPLEMENTED / REGRESSION VERIFIED / REAL BROWSER VERIFICATION PENDING`
- `E2E-012 = BLOCKED`
- `Phase 2.7B = INCOMPLETE / BLOCKED BY E2E-012`

DEFECT-021 is not declared FIXED or FROZEN. DEFECT-022/023/024 remain untouched.

## Interview asset

No Q&A was added because real browser closure is pending. The verified boundary is: browser persistence restores a user choice; it is never authorization, and backend ownership validation remains authoritative.

## Git

No commit, add, reset, restore, clean, or stash was executed.
