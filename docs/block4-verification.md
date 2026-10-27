# Block 4 verification — workflow integration

## Implemented scope

- Added persisted, advisory cross-bureau coordination requests tied to existing
  overlap candidates. A request records both case/bureau references, requester,
  reason, lifecycle response, and audit events. It grants no new case access and
  never changes case ownership/status automatically.
- Added `GET /api/cases/{case_id}/context` for one permission-scoped case detail
  payload (case, workflow history, accessible overlaps, alerts, coordination).
- Added authenticated bureau/officer reference endpoints for real workflow
  forms, rather than prompt-only identifiers.
- Reworked the frontend case workspace around API-backed case detail, labelled
  status/transfer/note/escalation forms, profile navigation, related overlap
  coordination actions, loading/error/success feedback, and existing reports.

## Requirement status

| Requirement | Status | Evidence |
|---|---|---|
| Case intake, unique server-side ID, initial event, validation | Implemented and verified | Existing lifecycle tests plus API-backed frontend form retained. |
| Case details, history, institution/alert/overlap context | Implemented and verified | New context endpoint test and live read-only request. |
| Status changes, notes, assignment/transfer, escalation | Implemented and verified | Existing Blocks 1–2 lifecycle/transfer/escalation tests remain green; UI controls call those APIs. |
| Persisted coordination request/response | Implemented and verified | New isolated end-to-end test checks creation, duplicate 409, receiving-bureau response, alert, audit, and hidden unrelated-bureau listing. |
| Human overlap review only; no automatic case outcome | Implemented and verified | Existing explainable overlap implementation retained; coordination service contains no case state/ownership mutation. |
| Alert lifecycle and explicit monitor | Implemented and verified | Existing Block 2 tests pass; UI retains on-demand monitor action. No scheduler/delivery claim. |
| Dashboard/reports/export permissions and CSV protection | Implemented and verified | Existing 10 Blocks 1–2 regressions pass; live summary reports 40 cases. |
| Institution-to-case navigation | Implemented, partially verified | API context/profile requests and production build pass. Browser click automation is unavailable. |
| Authorization/audit/data integrity | Implemented and verified | Direct API tests cover cross-bureau denial, duplicate prevention, safe scoped context, and immutable audit design. |
| Official registry, PostgreSQL, delivery, scheduler | Blocked by external dependency | No service/credentials supplied; not claimed. |

## Commands completed

| Command | Result |
|---|---|
| `uv run ruff check .` | Passed after Block 4 changes. |
| `uv run python -m compileall -q app tests alembic` | Passed. |
| `uv run pytest -q tests/test_api.py tests/test_block2.py` | 10 passed, one non-failing upstream TestClient warning. |
| `uv run pytest -q tests/test_block3.py tests/test_isolation.py tests/test_block4.py` | 10 passed, same warning. |
| `DATABASE_URL=sqlite:///./block4-final-migration.db uv run alembic upgrade head; uv run alembic check` | Fresh isolated database migration succeeded; no drift. |
| `npm.cmd run build` from `frontend` | TypeScript and Vite production build passed. |
| Read-only live API/UI check | Backend health `ok`, demo login true, 6 bureaus, 40 case-list/dashboard totals, API case context/history and institution profile succeeded, frontend HTTP 200. |

The suite now contains 20 tests (18 prior tests plus 2 Block 4 workflow tests).
All mutation tests use the Block 3 exact-path test-database guard.

## Data safety and migration

Migration `b4a1c2d3e4f5_add_coordination_requests.py` is additive. It was first
tested on a fresh isolated SQLite database, then applied to the known synthetic
demo database only after a read-only login/count check showed 40 existing cases.
After upgrade, the demo still had 40 cases and 20 institutions; no reset, drop,
or seed operation was performed in Block 4.

## Targeted repair update

The formerly missing coordination-response and alert acknowledge/resolve UI
controls are implemented in `frontend/src/App.tsx` using the existing backend
endpoints. Alert lifecycle idempotence/invalid-transition checks were added to
the backend and isolated tests. See [block4-repair-verification.md](block4-repair-verification.md).

## Known limits

- The browser UI was built and its real API routes were smoke-tested, but no
  browser automation facility was available to click every control.
- Coordination has a small explicit lifecycle (pending, responded, more
  information requested, resolved), not an asserted official AICTE workflow.
- No official registry, PostgreSQL service, continuous scheduler, email/SMS,
  external identity system, or production deployment was tested.
