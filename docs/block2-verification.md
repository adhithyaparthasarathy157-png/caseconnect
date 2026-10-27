# Block 2 verification

## Results matrix

| Requirement | Result | Evidence |
|---|---|---|
| Explainable, institution-bounded overlap detection | PASS | Deterministic identity/category/reference/date rules plus local text similarity; cross-institution false-positive test |
| Human overlap review and audit | PASS | Pending queue, confirm/dismiss/coordination actions, audit event test |
| Deadline monitoring and deduplicated alerts | PASS | Explicit monitor endpoint, unique dedupe keys, acknowledgement/resolution API tests |
| Permission-scoped analytics and CSV | PASS | Live database summary, accessible-case export, regional isolation test |
| General audit trail | PARTIAL | Case/institution/overlap/alert/report events recorded and read-only endpoint; administrative user/bureau edits are not exposed in Block 1 |
| React frontend integration | PASS | Real centralized API client, login and data-backed screens; production build passed |
| Full reports requested (institution/bureau/ageing CSV variants) | PARTIAL | Summary plus case, bureau-summary, ageing and institution-history CSV endpoints work. The compact frontend currently exposes the case CSV control. |
| Continuous scheduler / external notification | NOT IMPLEMENTED | Only explicit safe monitor runs; no email/SMS service configured. |

## Commands and results

- `uv run ruff check .` — passed.
- `uv run pytest -q` — **9 passed**, one non-failing upstream Starlette TestClient deprecation warning.
- `uv run alembic upgrade head` and `uv run alembic check` on isolated SQLite database — migration applied; no schema drift.
- `npm run build` in `frontend` — passed.
- Live isolated-server check — health `ok`; seeded 40 cases; monitor processed 30 deadline-eligible cases; overlap refresh returned 46 advisory candidates; 53 alerts were present; Vite returned HTTP 200.

## Added functionality

- Migration `f3cf3fa5cbb8_add_intelligence_alerts_and_audit.py`.
- Explainable overlap candidates (`same institution` is mandatory; text alone cannot confirm unrelated institutions), human review and advisory-only coordination decisions.
- Alert monitor with configurable 1–60 day warning window, duplicate suppression, role-scoped lists and state updates.
- Permission-scoped analytics summary, CSV export and audit endpoint.
- React/Vite frontend at `frontend/`.

## Limitations

- All data is fictional synthetic demonstration data; no official registry, AICTE integration, email/SMS, or production scheduler exists.
- SQLite and the full backend workflow are verified locally. PostgreSQL driver is included, but no PostgreSQL server was supplied for live connection testing.
- The frontend shows live backend data and real actions, but advanced case creation/detail forms and charting are intentionally compact prototype implementations rather than a full production workflow designer.
