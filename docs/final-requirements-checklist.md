# Final requirements checklist — Blocks 1 to 3

Status reflects executed evidence from the 2026-10-27 closure audit. The supplied
project requirements and in-repository requirements audit are the available SIH
source material; no separate official registry specification is present here.

Block 4 update: additive, human-led coordination requests/responses and an
API-backed case-detail workspace were added and verified. The guarded suite now
contains 20 tests; see `docs/block4-verification.md` for exact evidence.

| Area / requirement | Status | Evidence / limitation |
|---|---|---|
| Isolated test database, fail-fast test safety and failure cleanup | PASS | Exact-path SQLite guard rejects demo paths and all non-SQLite URLs; controlled failing-test cleanup proved no demo impact. |
| Institution registry: create/read/edit/search, normalized Permanent-ID uniqueness | PASS | Case/whitespace canonicalization, useful 409 conflicts, update rollback, and concurrent database-constraint test pass. |
| Missing/unverified and genuinely distinct IDs | PASS | Blank ID safely becomes `null`; verification flag is explicitly local; punctuation is not guessed or merged. |
| Institution profile, consolidated cases, status totals and overlap references | PASS | Empty/unknown/multi-case/scoped/overlap tests pass; live profile bucket total equals live case total. |
| Institution regional/bureau authorization and protected audit records | PASS | Regional profile denial, bureau case redaction, unauthorized audit list denial, and no audit mutation route verified. |
| Institution browser workflows and profile-case opening | PARTIAL | Built React implementation routes filters and selected profile cases to real API calls. Browser control clicks were not automated because no browser-test facility is configured. |
| Connected case-detail workflow and related navigation | Implemented, partially verified | `GET /api/cases/{case_id}/context` plus frontend detail, transfer/status/note/escalation and institution navigation use real APIs. Browser-control automation remains unavailable. |
| Cross-bureau coordination requests and responses | Implemented and verified | Additive `coordination_requests` migration, role-scoped APIs, duplicate protection, alerts and audit coverage pass in `tests/test_block4.py`. Requests are advisory only. |
| Frontend coordination response and alert acknowledgement/resolution controls | Implemented, partially verified | Dedicated controls call existing APIs, validate/disable/refresh server state, and backend API lifecycle tests pass. Browser click automation remains unavailable. |
| Case metadata, identifiers, lifecycle, assignment, transfer, escalation and history | PASS | Blocks 1 regression module: 7 tests passed. |
| Explainable same-institution overlap detection and human review | PASS | Block 2 overlap refresh/review/audit tests passed. |
| Alerts, deadlines, acknowledgement and scoped visibility | PASS | Block 2 alert/monitoring regression passed. Continuous scheduling/notifications remain external deployment work. |
| Analytics, dashboard filters, reports and safe CSV exports | PASS | Analytics/filter/export tests passed, including formula-leading CSV cell protection; live dashboard endpoint returned 40 seeded cases. |
| Authentication, JWT, bureau/region restrictions and error handling | PASS | Auth/permission tests pass; live demo JWT login works; cross-region profile request returns 403. |
| Migrations, schema drift, seed and demo database health | PASS | Fresh isolated SQLite migration and Alembic check pass; recovered demo has required tables, revision `f3cf3fa5cbb8`, constraints/indexes, 20 institutions, and 40 synthetic cases. |
| Frontend production build and serving | PASS | `npm.cmd run build` passed; running Vite frontend returned HTTP 200. |
| Official AICTE Permanent-ID verification | BLOCKED | No authorized registry/API, trusted format, credentials, or data source was supplied. |
| PostgreSQL service verification | BLOCKED | PostgreSQL is configurable but no server or credentials were supplied. |
| Pagination for large institution directories | PARTIAL — optional | Current synthetic 20-record directory has API-backed search/filters; pagination remains a scalability enhancement. |
| Continuous scheduler/email/SMS delivery | PARTIAL — optional/external | Explicit monitor API is tested. Production scheduling and delivery credentials are external deployment work. |

## Block 5 final update

- 22 isolated backend tests were collected and passed in serial groups: 7 API,
  8 Blocks 2–3, and 7 Block 4/isolation tests.
- Coordination and alert controls retain confirmed API responses after mutation.
- Institution profiles now return scoped related coordination records alongside
  overlap records. Browser-click automation remains unavailable.

## Final executed test coverage

- 21 tests collected after the independent audit added transfer-integrity coverage.
- 10 passed: `tests/test_api.py` and `tests/test_block2.py`.
- 8 passed: `tests/test_block3.py` and `tests/test_isolation.py`.
- One upstream Starlette TestClient deprecation warning occurred in each normal regression run; no normal regression test failed.
- A separate deliberate failure probe was executed to verify test cleanup. Its failure was expected and is documented in [block3-verification.md](block3-verification.md).
- Independent Blocks 1–4 audit evidence: [blocks1-4-audit-report.md](blocks1-4-audit-report.md).
