# AICTE CaseConnect

Synthetic Demonstration Data — Not Official AICTE Records.

This SIH prototype includes a FastAPI API and React/Vite administrative client. It uses PostgreSQL when `DATABASE_URL` is configured and SQLite by default for local demonstration. Overlap suggestions and deadline windows are explainable configurable prototype features, not official AICTE policy or registry integrations.

## Quick start

```powershell
uv sync --group dev
Copy-Item .env.example .env
uv run alembic upgrade head
# Seed only a new or verified-empty local demonstration database.
# It is repeatable, but do not use it to reset an existing database.
uv run python -m app.seed
uv run uvicorn app.main:app --reload
```

Set `JWT_SECRET_KEY` in `.env` to a unique value of at least 32 characters before starting. Open `http://127.0.0.1:8000/` for API links or `http://127.0.0.1:8000/docs` for documentation. The seed command prints development login credentials. Change the JWT secret and all credentials before any deployment.

## Database commands

```powershell
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
uv run alembic downgrade -1
```

For PostgreSQL set, for example, `DATABASE_URL=postgresql+psycopg://user:password@localhost/caseconnect`. The PostgreSQL driver is included in the project dependencies.

## Tests

```powershell
uv run pytest
```

Tests force a separate `.pytest-caseconnect.db` and reject the configured demo
database and non-SQLite deployment URLs. Never point test cleanup at a demo or
production database.

## API outline

- `GET /health`
- `POST /api/auth/token`
- `GET|POST|PATCH /api/institutions`
- `GET /api/institutions/{institution_id}/cases`
- `GET|POST|PATCH /api/cases`
- `GET /api/cases/{case_id}/history`
- `GET /api/cases/{case_id}/context`
- `POST /api/cases/{case_id}/actions`
- `GET /api/reference/bureaus` and `GET /api/reference/officers?bureau_id=`
- `GET|POST /api/coordination` and `POST /api/coordination/from-overlap/{id}`

All `/api` routes require a bearer token except `/api/auth/token`.

## Portals & Demo Accounts

The application features a landing page (`/`) offering two entry points:

1. **Admin Portal** (`/admin/login` or via `/`):
   - For administrators and AICTE officers managing cases, bureau transfers, overlaps, alerts, reports, and audit trails.
   - Demo credentials: `admin@demo.example.com` / `DemoPass!2026`

2. **Institution User Portal** (`/institution/login` or via `/`):
   - For authorized institution representatives. Scoped strictly to applications, alerts, and details belonging to their linked institution.
   - Server-side isolation prevents viewing or mutating cases from other institutions.
   - Submissions automatically resolve institution assignment and originating bureau server-side.
   - Demo credentials: `institution.rep@demo.example.com` / `InstitutionDemo!2026` (linked to `DEMO-AICTE-0001` / *Fictional North Institute of Technology 01*).

### Institution Portal APIs

- `GET /api/portal/overview`: Institution-scoped counts (total applications, under review, action required) and recent applications.
- `GET /api/portal/applications`: Institution-scoped application list with optional `case_id` search.
- `GET /api/portal/applications/{case_id}`: Detail view for an application with event timeline, institution profile, and alerts.
- `GET /api/portal/alerts`: Alerts specific to the representative's institution cases.
- `GET /api/portal/institution`: Profile of the representative's linked institution.

### Case receipt date

New cases use a required date-only `receipt_date` value (`YYYY-MM-DD`) rather
than a receipt timestamp. The user interface displays it as `DD-MM-YYYY`; the
historical `receipt_at` timestamp remains in the database only for legacy
reporting compatibility. Direct local case links use
`http://127.0.0.1:5173/cases/{case_id}` after authentication.

## Frontend

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

The frontend is served at `http://127.0.0.1:5173`, uses `VITE_API_BASE_URL`, and calls the real API. Build it with `npm run build`.

## Block 2 APIs

- `GET /api/overlaps`, `POST /api/overlaps/refresh`, `POST /api/overlaps/{id}/review`
- `POST /api/monitoring/run?warning_days=7` (explicit repeatable monitor, not a continuous scheduler)
- `GET /api/alerts`, `POST /api/alerts/{id}/read|acknowledge|resolve`
- `GET /api/analytics/summary`, `GET /api/analytics/cases.csv`
- `GET /api/audit-events` (authorized roles only)

## Implemented workflow

The connected prototype supports synthetic case intake, validated status
changes, notes, assignment/transfer actions, escalation, immutable case history,
institution profiles, advisory overlap review, and persisted cross-bureau
coordination requests/responses. Coordination is tied to a human-reviewed
overlap and never automatically transfers, merges, rejects, closes, or disposes
of a case. The deadline monitor is explicitly invoked through its API; no
continuous scheduler, email, or SMS delivery is claimed.

The dashboard definition of **pending** is every status except Disposed and Closed; **overdue** means the expected disposal date is before now and the case is not disposed/closed. These are reporting definitions only, not official SLA rules.
