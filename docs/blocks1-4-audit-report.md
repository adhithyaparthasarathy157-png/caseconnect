# Blocks 1–4 complete audit report

Audit date: 2026-10-27. This was an audit-and-repair pass; no Block 5 work was
started.

## Overall result

**Passed with documented limitations.** All automated backend checks, fresh
isolated migration checks, frontend production build, and read-only live API
checks completed successfully. Browser automation is unavailable, so a build or
API response is not represented as browser-click verification.

## Inspection scope

The audit reviewed the FastAPI application, configuration/database/session
setup, JWT/dependencies, models, schemas, services, every route module,
monitoring, intelligence, migrations (including `b4a1c2d3e4f5`), guarded test
configuration, all tests, React/Vite app/API client/build scripts, README, and
Blocks 1–4 verification documentation. No Git repository is present in this
workspace, so a Git worktree status could not be obtained.

## Defect repaired

| Defect | Reproduction and root cause | Repair and regression protection |
|---|---|---|
| Same-bureau transfer mutated a case | The transfer service accepted the current bureau as target, then marked the case Transferred and cleared its assignment. | `app/services.py` rejects this input with 422 before mutation. `tests/test_block4.py::test_same_bureau_transfer_is_rejected_without_case_or_history_change` asserts unchanged state and history. |

An interrupted aggregate test command briefly showed a 401 after login. The
exact isolated test and both completed module suites passed on rerun; the issue
was not reproducible and no authentication behavior was weakened.

## Completed checks

| Check | Result |
|---|---|
| Test collection | 21 tests collected after the transfer-integrity regression test was added. |
| `tests/test_api.py tests/test_block2.py` | 10 passed, 1 upstream TestClient deprecation warning. |
| `tests/test_block3.py tests/test_block4.py tests/test_isolation.py` | 11 passed, same warning. |
| Ruff and Python compilation | Passed. |
| Fresh isolated SQLite upgrade and Alembic drift check | Passed; no schema drift. |
| Frontend TypeScript/Vite production build | Passed. |

## Data safety and live evidence

The test guard forces the exact `.pytest-caseconnect.db`, rejects any other
SQLite path and all non-SQLite URLs, and cleanup tests remain green. Read-only
demo inspection found `sqlite:///./caseconnect.db` at head `b4a1c2d3e4f5` with
40 synthetic cases and 20 institutions before the audit; live API retrieval
still returned 40 cases afterward. No reset, truncate, drop, reseed, or demo
mutation occurred.

Read-only live results: health `ok`; missing and malformed tokens return 401;
documented demo login works; case context, institution profile, analytics and
CSV export work; a North user requesting a South profile gets 403; Vite returns
HTTP 200.

## Targeted repair update

The previously documented compact-UI gap is repaired: coordination response
and alert lifecycle controls now call the existing APIs and refresh server
state. Alert duplicate actions are idempotent/rejected as appropriate and are
covered by a new isolated lifecycle test. See
[block4-repair-verification.md](block4-repair-verification.md).

## Known limitations

- Browser automation remains unavailable, so browser clicks are not claimed
  verified even though the production build and API integration tests pass.
- No browser automation, official AICTE registry, PostgreSQL service,
  continuous scheduler, email/SMS delivery, or production deployment was
  available or claimed.

## Service status

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- API documentation: `http://127.0.0.1:8000/docs`

## Superseded by Block 5

The final Block 5 verification added scoped institution-profile coordination
references and refreshed post-mutation UI state. Current final evidence is in
`docs/block5-final-verification.md` and `docs/block5-requirement-validation.md`.
