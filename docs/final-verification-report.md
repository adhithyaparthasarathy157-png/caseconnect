# Final verification report — Block 3 closure

## Block 4 update

Block 4 added an API-backed case detail/context workflow, authenticated bureau
reference data, and persisted advisory coordination request/response records.
The additive migration is `b4a1c2d3e4f5`; it preserved the known synthetic demo
counts (40 cases and 20 institutions). The guarded suite now has 20 tests: 10
Blocks 1–2 tests and 10 Blocks 3/isolation/Block 4 tests completed successfully.
See [block4-verification.md](block4-verification.md) for exact evidence.

## Outcome

Block 3 is complete for the locally runnable prototype. The guarded regression
suite covers all 18 collected tests and completed with **18 passed** (10 + 8
completed runs). The only test warning is an upstream Starlette TestClient
deprecation warning. This historical Block 3 statement is superseded by the
Block 4 update above; no Block 5 work was started.

## Verified environment

| Check | Actual result |
|---|---|
| Demo database schema | Required tables present; Alembic revision `f3cf3fa5cbb8`; Permanent-ID unique constraint and expected indexes present. |
| Demo synthetic records | Live API login succeeded; 20 institutions and 40 cases are usable. |
| Backend live smoke | `/health` returned `ok`; dashboard total and case listing total were both 40. |
| Institution live smoke | Permanent-ID + North + Active filter returned 1 result; profile reported 4 cases and status buckets totaling 4. |
| Authorization live smoke | North regional user received 403 for a South institution profile. |
| Frontend live smoke | Running frontend returned HTTP 200. |
| Production build | `npm.cmd run build` passed. |
| Fresh migration / drift | Isolated `block3-closure-migration.db` upgraded to head; `alembic check` reported no new upgrade operations. |

## Test safety repair

The original test fixture could drop application tables through the configured
engine. This closure replaces it with an enforced guard in `tests/conftest.py`:

- tests force one absolute SQLite file: `.pytest-caseconnect.db`;
- any other SQLite path, including `caseconnect.db`, is rejected;
- non-SQLite deployment URLs are rejected;
- schema create/drop occurs only after that guard runs, around every test.

The guard is tested directly. A separate controlled test wrote a synthetic row
and intentionally raised; its expected failure was followed by an inspection
showing no test tables, while the live demo still authenticated and listed 40
cases. This is the evidence for cleanup-on-failure, not a product-test failure.

## Commands and results

```powershell
uv run ruff check .
# passed

uv run pytest --collect-only -q
# 18 tests collected

uv run pytest -q tests/test_api.py tests/test_block2.py
# 10 passed, 1 warning, 22.88s

uv run pytest -q tests/test_block3.py tests/test_isolation.py
# 8 passed, 1 warning, 10.30s

$env:DATABASE_URL = 'sqlite:///./block3-closure-migration.db'
uv run alembic upgrade head
uv run alembic check
# passed; no schema drift

cd frontend
npm.cmd run build
# passed
```

A single `uv run pytest -q` invocation was attempted but the execution host
ended it at its command-window boundary before a final result. It is therefore
not claimed as a pass. The two completed module runs above cover exactly the 18
tests listed by collection, with no skipped tests.

## Repairs in this audit

- Centralized safe test database isolation and added a tested failure-cleanup probe.
- Expanded Block 3 integrity/profile/audit/concurrency tests.
- Added frontend institution region/status query wiring and profile-case navigation to the Cases view.
- Recovered the local synthetic demo schema using its existing Alembic history after confirming only the version table remained, then populated it only with the documented synthetic seed.
- Updated all verification documents with executed evidence.

## Remaining limitations

- Official AICTE registry verification is unavailable and is not claimed.
- PostgreSQL, production scheduler, and notification delivery services were not available for verification.
- The frontend was built and served, and its API calls were live-checked; its individual browser controls were not automated because this environment has no browser-test facility.
- Institution-list pagination remains an optional scalability enhancement.

See [block3-verification.md](block3-verification.md) and
[final-requirements-checklist.md](final-requirements-checklist.md) for the
requirement-level statuses.

## Independent Blocks 1–4 audit update

The audit added and passed a regression test for same-bureau transfer rollback:
such an action now returns 422 without modifying the case or its history. It
completed 21 collected tests in two green module runs (10 + 11), lint,
compilation, fresh isolated migration/drift checks, frontend production build,
and read-only live API/frontend smoke checks. The demo stayed at 40 cases and
20 institutions. The compact UI still lacks dedicated coordination-response and
alert acknowledgement/resolution controls; this is documented as PARTIAL rather
than claimed verified. See [blocks1-4-audit-report.md](blocks1-4-audit-report.md).

## Block 4 targeted UI repair update

Coordination-response and alert acknowledge/resolve controls are now wired to
their existing authenticated APIs. A backend alert-lifecycle repair makes
duplicate acknowledgement idempotent and rejects invalid actions after
resolution; isolated authorization/persistence/audit tests passed. Fresh
isolated migration/drift and compilation checks passed, and a read-only demo
count remains 40 cases / 20 institutions. Frontend production build passed.
Browser automation remains unavailable, so these UI interactions are not
represented as browser-click verified. See
[block4-repair-verification.md](block4-repair-verification.md).

## Backend root-route diagnostic and repair (2026-10-27)

The listener on `127.0.0.1:8000` was the local CaseConnect Uvicorn process.
Before repair, only `GET /` returned FastAPI's normal 404 response; `/health`,
`/docs`, and `/openapi.json` returned 200, and `/health` reported a connected
database. This was not a router-registration, authentication, migration, or
database failure, but the missing browser landing route was repaired for the
local demonstration.

`app/main.py` now supplies `GET /`, returning the API name and links to
`/health`, `/docs`, and `/openapi.json`. The restarted service logged successful
startup and served the repaired route.

| Verification | Result |
|---|---|
| Demo database | Read-only inspection: SQLite, Alembic `b4a1c2d3e4f5` (head), expected ten tables, Permanent-ID unique constraint, 40 synthetic cases, and 20 institutions. |
| Live endpoint checks | Root, health, docs, OpenAPI, demo login, case list/context, institution list/profile, coordination list, bureau/officer references, analytics summary, and cases CSV all returned real successful responses. |
| Test collection | 22 tests collected. |
| `tests/test_api.py` | 7 passed, 1 upstream TestClient deprecation warning. |
| `tests/test_block2.py tests/test_block3.py` | 8 passed, 1 warning. |
| `tests/test_block4.py tests/test_isolation.py` | 7 passed, 1 warning. |
| Lint and compilation | `uv run ruff check .` and `uv run python -m compileall -q app tests alembic` passed. |
| Fresh isolated migration | A temporary workspace SQLite database upgraded to head; `uv run alembic check` reported no new upgrade operations. |

No demo records were reset, seeded, dropped, or modified during this diagnostic.

## Block 5 final verification (2026-10-27)

Block 5 repaired profile-to-coordination traceability and stale selected state
after coordination/alert mutations. The final guarded suite collected 22 tests
and all passed in serial isolated runs (7 API, 8 Blocks 2–3, 7 Block
4/isolation); each emitted only an upstream TestClient deprecation warning.
Ruff, Python compilation, TypeScript/Vite production build, fresh isolated
SQLite migration, and Alembic schema-drift check passed. Read-only live API
verification returned 200 for root, health, docs, login, case list/context,
institution profile, analytics, CSV export, coordination, and alerts, while
preserving the 40-case/20-institution synthetic demo. Browser automation and
external AICTE/PostgreSQL/notification services remain unavailable and are not
claimed. See [block5-final-verification.md](block5-final-verification.md).
