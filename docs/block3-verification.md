# Block 3 verification — closure audit

Audit date: 2026-10-27. All records used for mutation tests were synthetic and
were confined to the dedicated test SQLite database.

## Requirement results

| Requirement | Status | Confirmed evidence |
|---|---|---|
| Test database isolation and cleanup | PASS | `tests/conftest.py` forces an absolute `.pytest-caseconnect.db` URL before application imports, rejects every other SQLite path and every non-SQLite URL, and recreates/drops only that schema for every test. Guard tests passed. A controlled failing test inserted a record, raised, then left the test database with `[]` tables; the demo API still logged in and listed 40 cases. |
| Permanent-ID whitespace/case normalization and duplicate rejection | PASS | `tests/test_block3.py` verifies canonical lookup, 409 duplicate response, and update conflict. The database unique constraint rejects simultaneous inserts. |
| Permanent-ID format safety | PASS | Only whitespace collapsing and letter-case normalization are applied. A punctuation-distinct value remains distinct; no unsupported official AICTE format is inferred. Blank IDs normalize to `null`; verification remains a local data flag. |
| Transactional failed institution update | PASS | A PATCH to another institution's canonical ID returns 409; the original ID and name are retrieved unchanged afterward. |
| Consolidated institution profile | PASS | Empty, unknown, multi-case, status-bucket, related-overlap, and no-duplicate case cases are covered in focused tests. Live seeded profile returned 4 cases and status buckets totaling 4. |
| Profile authorization and restricted details | PASS | A North regional user received 403 for a South profile. A bureau without access sees no cases or related overlaps in an otherwise visible institution profile. |
| Institution audit protection | PASS | Creation/update audit entries include actor, entity ID, timestamp, and safe before/after values. Password material is absent from tested details; non-authorized audit listing is 403 and there is no audit mutation route. |
| Institution search/filter/profile case navigation UI | PARTIAL | Backend search by Permanent ID, region, and status is live-checked. The React UI passes these filters and has an `openProfileCase` handler that fetches the selected case in the Cases tab; TypeScript/Vite build passed. No browser automation facility is configured, so clicking the controls was not independently automated. |
| Blocks 1 and 2 regressions | PASS | Auth, authorization, case lifecycle/transfer/escalation/history, overlap review, alerts, analytics, CSV exports, and formula-injection protection all passed in the guarded suite. |
| Official AICTE ID verification or registry lookup | BLOCKED | No authorized official registry, identifier specification, credential, or data-sharing integration was supplied. The application deliberately makes no official-verification claim. |
| PostgreSQL deployment verification | BLOCKED | The project is PostgreSQL-configurable, but no PostgreSQL service or credentials were provided. SQLite-only local verification was performed. |

## Executed verification

| Command | Outcome |
|---|---|
| `uv run ruff check .` | Passed. |
| `uv run pytest --collect-only -q` | Completed: 18 tests collected. |
| `uv run pytest -q tests/test_api.py tests/test_block2.py` | Completed: 10 passed in 22.88s; one non-failing upstream Starlette TestClient deprecation warning. |
| `uv run pytest -q tests/test_block3.py tests/test_isolation.py` | Completed: 8 passed in 10.30s; same warning. Together these completed runs execute all 18 collected tests. |
| `CASECONNECT_TEST_FAILURE_PROBE=1 uv run pytest -q tests/test_isolation.py::test_failure_cleanup_probe` | Expected failure (1 failure) after an intentional insert/raise. It is a safety probe, not a product-test failure. A subsequent read of the test DB showed no tables; demo login/count remained unchanged. |
| `DATABASE_URL=sqlite:///./block3-closure-migration.db uv run alembic upgrade head; ... alembic check` | Completed on a new isolated SQLite file; no schema drift. |
| `npm.cmd run build` in `frontend` | Passed: TypeScript build and Vite production build completed. |
| Read-only live API/UI HTTP smoke test | Passed: API health `ok`; demo JWT login true; dashboard total 40; case listing total 40; filtered institution search 1; profile cases/status-bucket total 4/4; North-to-South profile 403; frontend HTTP 200. |

The single-command `uv run pytest -q` was not recorded as a pass because this environment ends that long command at its execution-window boundary before it prints a final summary. The two completed module commands above cover exactly the 18 tests reported by collection; no test was skipped.

## Demo database recovery and consistency

The local configured SQLite demo database was read-only inspected after recovery. It has all required application tables, Alembic revision `f3cf3fa5cbb8`, the `uq_institution_permanent_id` constraint, institution indexes including normalized-name and region/status, and case indexes including status/bureau and receipt-date. The synthetic seed data is usable: demo login succeeded, with 20 institutions and 40 cases exposed through the running API. No PostgreSQL database was contacted.

## Changes made during this closure

- Replaced the unsafe test-local cleanup fixture with `tests/conftest.py` centralized guard and cleanup fixture.
- Added `tests/test_isolation.py`, including URL-rejection and failure-cleanup probes.
- Expanded `tests/test_block3.py` for empty profiles, overlap visibility, failed-update rollback, concurrent uniqueness, punctuation distinction, and audit immutability.
- Added institution filter query wiring and profile-case navigation to `frontend/src/App.tsx`.
- Recovered the empty local synthetic demo schema through its existing Alembic history and documented synthetic seed; no external or production database was touched.
