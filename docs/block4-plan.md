# Block 4 plan — connected workflow and coordination

## Baseline and source of truth

The available source material is the supplied Block 4/SIH brief plus the
in-repository requirements audit. There is no standalone official AICTE policy
or registry specification in this workspace. Existing terminology, role names,
and transition rules will therefore be retained; this block will not claim
official verification, SLA, notification delivery, or registry integration.

The local demo database is a separate SQLite database with synthetic records.
Tests are guarded by `tests/conftest.py` and may mutate only
`.pytest-caseconnect.db`.

## Requirement map

| Area | Existing implementation | Block 4 work | Primary modules | Verification |
|---|---|---|---|---|
| Case intake, events, transitions, assignments and transfers | API/service and basic form/action controls exist; server validates bureau/officer and writes case events | Preserve rules; add useful detail data and real form controls without prompts | `services.py`, `routers/cases.py`, `App.tsx` | Lifecycle, invalid transition, assignment and transfer tests |
| Case details/navigation | Case response/history exist, but UI is minimal and lacks related links | Add API-backed detail panel with history, institution, overlap/alert/coordination context and navigation | case/overlap/alert routers, frontend | API workflow tests; production build; live smoke |
| Cross-bureau coordination | Overlap review can be marked `Coordination Requested`, but no request/response record exists | Add a small persistent coordination lifecycle tied to an overlap; protect case details by existing case visibility | new model/migration/router/service/schema/frontend | create/respond/duplicate/permission/visibility tests |
| Overlap review | Explainable, institution-bounded candidates and human review exist | Expose linked coordination state, reasoned actions, and detail navigation; preserve advisory-only behavior | overlap router, intelligence, frontend | overlap and coordination workflow tests |
| Alerts/escalation | Explicit monitor, dedupe, acknowledge/resolve and escalation event exist | Add case navigation and clear state display; keep on-demand monitor explicitly labelled | alerts/monitoring/frontend | monitor/alert lifecycle regressions |
| Analytics/reports | Scoped summary and protected CSV exports exist | Retain server filtering; expose only existing data and make report/overview loading states useful | analytics/frontend | existing analytics and CSV tests |
| Institution journey | Profile and API exist; frontend has basic case jump | Link cases and overlaps consistently through the details workflow | institutions/frontend | profile and navigation API checks |
| Audit and authorization | Immutable audit endpoint, case events, role/bureau/region checks exist | Audit coordination actions and verify denied requests create no success record | coordination service/router/tests | authorization and audit tests |
| Test/data safety | Block 3 exact-path guard is in place | Retain guard; test all new mutations through it only | `tests/conftest.py`, tests | guard and complete suite |

## Implementation sequence and acceptance criteria

1. Establish a non-mutating baseline: lint, guarded tests, build, migration
   head, and demo counts/API health.
2. Add an additive coordination-request table, migration, schemas, router, and
   authorization-aware service. A request has one overlap, source/recipient
   bureau inferred from the two related cases, reason, requester, status,
   response, and audit records. No case access is granted by the request.
3. Extend overlap/detail APIs with only authorized context necessary for
   navigation. Preserve the existing advisory-only overlap scoring and review
   decisions.
4. Replace prompt-only frontend workflow controls with labelled action forms,
   a detail panel, coordination controls, loading/error/success states, and
   API-backed navigation.
5. Add end-to-end backend tests for case lifecycle, transfer integrity,
   coordination lifecycle, authorization, audit, alerts and analytics.
6. Run guarded regression tests, lint/compile, fresh isolated migrations and
   drift checks, frontend production build, and read-only live smoke tests.

## Explicit non-goals / external limits

- No official AICTE Permanent-ID lookup or rules.
- No live PostgreSQL, email/SMS, scheduler, browser automation, or deployment
  claim without a supplied service.
- No automatic merge, close, reject, dispose, or transfer due to overlap score.
