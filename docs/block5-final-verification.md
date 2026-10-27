# Block 5 final verification

## Overall status

**Ready with limitations for SIH demonstration.** The local synthetic prototype
is functional and tested. Browser automation and external production services
are unavailable, so those are not claimed.

## Executed results

| Check | Actual result |
|---|---|
| Collection | 22 backend tests collected. |
| `tests/test_api.py` | 7 passed, 1 upstream TestClient deprecation warning. |
| `tests/test_block2.py tests/test_block3.py` | 8 passed, 1 warning. |
| `tests/test_block4.py tests/test_isolation.py` | 7 passed, 1 warning. |
| Ruff / compilation | `uv run ruff check .` and `uv run python -m compileall -q app tests alembic` passed. |
| Frontend | `npm.cmd run build` passed (`tsc -b` and Vite). |
| Fresh migration | Fresh `.block5-migration-check.db` upgrade and `uv run alembic check` passed with no schema drift. |
| Live demo API | Root, health, docs, login, cases, institution profile/context, analytics, CSV, coordination and alerts all returned successful real responses. |

The live read-only API check reported 40 cases, 20 institutions, Alembic head
`b4a1c2d3e4f5`, and no demo mutations. Coordination and alerts were empty in
the preserved demonstration dataset; lifecycle/authorization behavior was
verified only in the isolated test database.

## Files changed in Block 5

- `app/schemas.py`
- `app/routers/institutions.py`
- `frontend/src/App.tsx`
- `tests/test_block3.py`
- `docs/block5-requirement-validation.md`
- `docs/block5-final-verification.md`
- `docs/final-requirements-checklist.md`
- `docs/final-verification-report.md`
- `README.md`

## Demonstration checklist

1. Start the backend with `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`.
2. Start the frontend with `cd frontend; npm run dev`.
3. Sign in with the existing documented synthetic demo account from `app/seed.py`.
4. Show Overview real counts, then search an institution and open its profile.
5. Open a listed case, review history/context, and return to its institution.
6. Use a prepared isolated-test workflow to demonstrate notes, status/transfer validation, overlap review, coordination response, and alert lifecycle; do not mutate the preserved demo data for these steps.
7. Show Reports export and Audit as an authorized user; demonstrate restricted access with a scoped demo role if desired.

## Limitations

- No browser automation was available; UI interaction claims are limited to code
  integration, production build, and backend API verification.
- No official AICTE registry, PostgreSQL service, scheduler, email/SMS service,
  or production deployment was available or claimed.
