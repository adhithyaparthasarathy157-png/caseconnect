# Block 1 verification — 2026-10-27

The workspace has no frontend source. Verification used newly created, isolated SQLite audit databases and only synthetic records. Existing `caseconnect.db` was not overwritten.

| Requirement | Result | Verification evidence |
|---|---|---|
| Institution registry and Permanent ID uniqueness | PASS | Creation, retrieval and duplicate-ID conflict tested over API |
| Institution-wise case history | PASS | Institution cases endpoint tested after case creation |
| Unique case ID and metadata | PASS | Two created cases have different IDs; required-field validation tested |
| Bureau and assigned officer fields | PASS | Relationships persisted; assignment limited to active officer in current bureau |
| Status/action/deadline fields | PASS | Status update and action history tested |
| Cross-bureau overlap detection/linking | NOT IMPLEMENTED | No overlap model, service or API in Block 1 foundation |
| Human review of overlaps | NOT IMPLEMENTED | No review queue or decisions model |
| Chronological action/transfer history | PASS | Created, updated, note and transfer events persist |
| Assignment/reassignment/transfer/escalation | PASS | Assignment, transfer and escalation API paths tested |
| Dashboard metrics | NOT IMPLEMENTED | No analytics endpoints |
| Search and filters | PASS | Institution/case filters are implemented and case filtering tested |
| Deadline alerts | NOT IMPLEMENTED | Disposal date is stored; no monitor or alert system |
| Bureau/region/institution/status reports | NOT IMPLEMENTED | No reporting module/endpoints |
| Monthly/quarterly CSV export | NOT IMPLEMENTED | No export endpoint |
| JWT roles, bureau and regional permissions | PASS | Login, 403 bureau denial, origin-bureau spoof denial, and regional scope tested |
| Audit logging, validation and errors | PARTIAL | Case events and structured 4xx responses work; institution edits lack audit events |
| Frontend/backend/database integration | PARTIAL | Backend/database integration verified; no frontend exists in workspace |
| Repeatable synthetic data and setup | PASS | Seed rerun remains at 20 institutions and 40 cases |

## Executed checks

- `uv run python -m compileall -q app tests alembic`
- `uv run ruff check .` — passed
- `uv run pytest -q` — 7 passed (one non-failing Starlette TestClient deprecation warning)
- `uv run alembic upgrade head` and `uv run alembic check` — schema current, no drift
- Real Uvicorn HTTP checks: health, JWT login, institution creation, case creation/retrieval, status update, note, transfer, invalid transition (422), unauthorized bureau retrieval (403), and persistence after process restart.

## Audit repairs

- JWT secret is now mandatory and must be at least 32 characters; no known default secret remains.
- Non-administrative users must create cases only for their own originating and current bureau; regional officers are also constrained to their configured region.
- Assigned officers must be active and belong to the case's current bureau.
- The seed command now requires the schema migration to be applied rather than silently using `create_all`.
