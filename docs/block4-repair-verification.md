# Block 4 targeted repair verification

## Scope

This repair closes the two previously documented compact-UI gaps without adding
new workflow endpoints: coordination responses and alert acknowledgement/
resolution. It also hardens alert lifecycle semantics against double-clicks.

## Implemented UI behavior

- Case detail now lists accessible coordination requests. Selecting one opens
  its request/case IDs, reason, current status, existing response, and a
  labelled response form using `POST /api/coordination/{id}/respond`.
- The form validates a two-character response, disables duplicate submission,
  preserves input after a recoverable failure, refreshes server context after
  success, and reports backend authorization/validation errors.
- Alert lists (both case context and Alerts tab) now open an alert detail card
  with actual title/message/state and **Acknowledge** / **Resolve** controls.
  Controls use `POST /api/alerts/{id}/acknowledge` and `/resolve`, disable when
  unavailable or pending, and refresh from the backend after confirmation.

## Backend lifecycle repair

`app/routers/alerts.py` now makes read/acknowledge idempotent and rejects
resolve-after-resolve or acknowledge-after-resolve with HTTP 422. This prevents
duplicate audit records or contradictory state from repeated clicks.

## Verification

| Check | Result |
|---|---|
| `uv run ruff check .` | Passed. |
| `uv run pytest -q tests/test_block2.py tests/test_block4.py` | 7 passed; one upstream TestClient deprecation warning. |
| `uv run pytest -q tests/test_block3.py tests/test_block4.py tests/test_isolation.py` | 12 passed; same warning. |
| `npm.cmd run build` in `frontend` | TypeScript/Vite production build passed. |
| Read-only live API smoke | Backend health `ok`, demo login true, coordination list and alerts returned real empty lists, case context succeeded, frontend HTTP 200. |

`test_alert_actions_are_authorized_persistent_and_idempotent` verifies a
synthetic alert created through the existing escalation workflow: unauthorized
acknowledgement is 403; acknowledgement persists; duplicate acknowledgement
creates no extra audit event; resolution persists; repeated resolution and
acknowledge-after-resolve are 422.

`test_cross_bureau_coordination_is_persisted_authorized_and_audited` continues
to verify response authorization, persistence, duplicate prevention, alerts,
and audit records through the existing coordination API.

## Limits

No browser automation tool is configured, so browser-click execution is not
claimed. The production build and live API/HTTP checks passed; backend behavior
is covered by isolated API tests. No demo records were created, reset, or
modified during this repair.
