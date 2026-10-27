# AICTE CaseConnect requirements audit

Audit date: 2026-10-27. The workspace was empty at the start of this block: no repository, frontend, backend, database, environment file, or tests existed. Therefore there was no pre-existing implementation to validate or preserve.

| Official requirement | Current implementation status | Evidence | Missing functionality or defect | Recommended implementation |
|---|---|---|---|---|
| Institution registry with verified Permanent ID | Implemented but not verified | `app/models.py`, institutions API, uniqueness test | Verification flag is self-reported; no official AICTE registry integration | Add official data-import approval workflow later |
| Consolidated institution-wise complaint history | Implemented but not verified | `GET /api/institutions/{id}/cases` | No frontend view or dedicated endpoint test | Build institution profile UI |
| Unique case identifiers and complete metadata | Implemented and verified | `Case.case_id`, `app/services.py`, API test | Sequence generation is not distributed-lock safe | Use database sequence/UUID strategy for multi-worker deployment |
| Current/originating bureau and officer | Implemented but not verified | `Case` model and case schemas | No dedicated assertion of each association | Add bureau/officer administration UI |
| Status, actions and disposal date | Implemented but not verified | `Case` model, PATCH/action routes | No dedicated action/deadline assertion | Surface deadline indicators in UI |
| Cross-bureau overlap detection and related links | Missing | No overlap tables/service | Required intelligence feature not in this block | Add candidate scoring, review queue and case-link table |
| Human review of overlaps | Missing | No review endpoint/model | Required workflow not in this block | Add reviewer decisions with audit events |
| Chronological case action/transfer history | Implemented and verified | `CaseEvent`, history endpoint, persistence test | None in foundation scope | Display timeline in frontend |
| Assignment, reassignment, transfer and escalation | Implemented but not verified | `POST /api/cases/{id}/actions`, transition service | Transfer is tested; assignment/reassignment/escalation need expanded scenario tests | Add notification and escalation policy configuration |
| Dashboard metrics from actual records | Missing | No analytics routes | No analytics layer | Add aggregate SQL queries and dashboard routes |
| Search and filters | Implemented and verified | institution/case query parameters, API filter test | Full-text search and compound UI filters absent | Add database-specific full-text indexing if needed |
| Deadline monitoring and actionable alerts | Missing | Deadline is stored only | No scheduler/alert model | Add overdue query, alert records and notification adapter |
| Bureau/region/institution/status reports | Missing | No reports module | No report endpoints | Add scoped aggregate report endpoints |
| Monthly/quarterly reports and CSV export | Missing | No export endpoint | No reporting/export service | Add CSV streaming and period aggregation |
| Authentication and role/bureau/region permissions | Implemented and verified | JWT, password hashing, dependency checks, restriction test | User lifecycle endpoints not yet exposed | Add administrator-only user provisioning/reset workflow |
| Audit logging, validation and error handling | Partially implemented | Case events, Pydantic schemas, structured error handlers | Institution edits are not separately audit logged | Add general audit-event table/service |
| Frontend-to-backend-to-database integration | Partially implemented | Migrated SQLite API checked with authenticated case list | No frontend existed in workspace | Build frontend in a later block and wire it to the API |
| Repeatable synthetic data and reproducible setup | Implemented and verified | `app/seed.py`, `pyproject.toml`, seed repeatability test | Uses fixed demo credentials intentionally | Replace with deployment provisioning before production |

The dataset and all seed records are explicitly fictional: **Synthetic Demonstration Data — Not Official AICTE Records**.
