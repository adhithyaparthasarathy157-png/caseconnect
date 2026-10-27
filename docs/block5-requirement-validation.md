# Block 5 requirement validation

Verification date: 2026-10-27. The available requirements source is
`docs/requirements-audit.md` plus the supplied project blocks; no separate
official SIH problem-statement file is present. All records described below are
synthetic demonstration data, not official AICTE data.

| Requirement summary | Implementation and UI/API | Authorization and evidence | Status / limitation |
|---|---|---|---|
| Institution registry and Permanent ID | Institution directory/profile in `frontend/src/App.tsx`; `/api/institutions` and `/profile` | Manager-only writes, regional profile scope; `test_block3.py` | Implemented and verified. Registry verification is not claimed. |
| Consolidated institution case history | Profile case/status totals, overlap and coordination references | Case visibility is filtered by role/bureau/region; `test_block3.py` | Implemented and verified by API/tests; browser clicking unautomated. |
| Case intake, lifecycle and history | Case form/detail; `/api/cases`, PATCH, actions, history/context | Case creation/modification is scope checked; `test_api.py`, `test_block4.py` | Implemented and verified. |
| Assignment, transfer, escalation | Case actions API/detail workflow | Target bureau/officer checks; same-bureau transfer rejection test | Implemented and verified. |
| Explainable overlap and human review | Overlaps screen; `/api/overlaps`, refresh/review | Reviewer permissions and duplicate constraints; `test_block2.py` | Implemented and verified. Suggestions are not automatic decisions. |
| Cross-bureau coordination | Coordination section in case context; `/api/coordination/*` | Receiving-bureau/admin response enforcement, audit, duplicate prevention; `test_block4.py` | Implemented and verified by isolated API tests; browser control clicks unautomated. |
| Deadline alerts and lifecycle | Alert section and `/api/alerts/*` | Scoped alert visibility; acknowledgement idempotence, resolution transition/audit tests | Implemented and verified by isolated API tests; browser control clicks unautomated. |
| Dashboard, analytics and exports | Overview/Reports; `/api/analytics/summary` and CSV routes | Results are scope-filtered; formula protection tests in `test_block2.py` | Implemented and verified. |
| Authentication, authorization and audit | Login/session storage, protected APIs, audit view | JWT, bureau/region restrictions, immutable audit read API; all module tests | Implemented and verified. |
| Migration and test isolation | Alembic plus guarded `.pytest-caseconnect.db` fixture | Isolation tests and fresh migration/drift check | Implemented and verified. |
| Official ID verification / registry | Local normalized ID and explicit disclaimer only | No supplied authoritative service or credentials | Blocked by external dependency. |
| PostgreSQL, scheduler, email/SMS | Configurable database and explicit monitor endpoint only | No service/credentials available | Blocked by external dependency. |

## Block 5 repairs

- Institution profiles now expose authorization-filtered `related_coordination`
  records rather than implying coordination is part of overlap-only data.
- Coordination and alert detail controls retain the confirmed server response
  after a successful mutation, preventing stale selected state.
- The profile regression test now proves coordination visibility and restricted
  users receive no coordination references.
