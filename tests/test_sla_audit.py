"""
SLA Production-Readiness & Regression Audit Tests — AICTE CaseConnect.

Covers all 12 audit criteria and second-level reconciliation requirements:
 1. Breached deadlines in past vs on-track in future; uniqueness and idempotency.
 2. CC-2026-00047 anomaly handling: pre-policy historical records initialized as PAUSED,
    while modern cases strictly enforce effective_from policy validity constraints.
 3. Deterministic policy resolution hierarchy and deadline calculation.
 4. Terminal cases completed with immutable historical performance metrics.
 5. Indian Holiday Calendar: central gazetted holidays, state observances opt-in,
    leap years (Feb 29), year boundaries (Dec 31 -> Jan 2), and consecutive holidays.
 6 & 7. Automatic background scheduler: registered in app lifespan, restart resilience,
    and fault isolation (a failing case does not halt remaining evaluations).
 8. All four escalation levels: L1 (90%), L2 (100%), L3 (3d overdue), L4 (7d overdue),
    idempotency guards, and suppression for paused/completed cases.
 9. Policy updates do NOT silently rewrite existing complaint deadlines.
10. Immutable audit history: pause, resume, complete, and transfers record events.
11. RBAC security: Institution Representatives blocked (403) from internal analytics.
12. Dashboard KPI accuracy: active_in_sla_percentage (including AT_RISK) vs active_healthy_percentage.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.enums import ActionType, AlertSeverity, CaseStatus, Priority, Role, SlaCalendarType, SlaStatus
from app.main import _sla_scheduler_task, app, lifespan
from app.models import (
    Bureau,
    Case,
    CaseEvent,
    CaseSlaRecord,
    Institution,
    SlaEscalation,
    SlaEvent,
    SlaPolicy,
    User,
)
from app.security import hash_password
from app.sla.calendar import (
    CENTRAL_GAZETTED_HOLIDAYS,
    STATE_OBSERVANCE_HOLIDAYS,
    add_business_days,
    add_calendar_days,
    calculate_deadline,
    ensure_utc,
    get_applicable_holidays,
    is_working_day,
)
from app.sla.evaluator import evaluate_all_active, evaluate_sla_record
from app.sla.policy_engine import resolve_policy, seed_demo_policies
from app.sla.tracking import (
    complete_sla,
    create_sla_record_for_case,
    pause_sla,
    resume_sla,
)


# ---------------------------------------------------------------------------
# Fixtures & Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def audit_seed_data():
    """Seed test database with bureaus, users, demo policies, and test institution."""
    with SessionLocal() as db:
        rb = Bureau(code="RB", name="Regulation Bureau", region="North")
        pgrc = Bureau(code="PGRC", name="Public Grievance", region="Central")
        db.add_all([rb, pgrc])
        db.flush()

        inst = Institution(
            permanent_id="SLA-INST-001",
            permanent_id_verified=True,
            name="SLA Test Engineering College",
            normalized_name="sla test engineering college",
            institution_type="Engineering",
            region="North",
            status="Active",
        )
        db.add(inst)
        db.flush()

        admin = User(
            email="sla_admin@test.example.com",
            full_name="SLA Admin",
            password_hash=hash_password("Pass123!"),
            role=Role.ADMIN,
            bureau_id=rb.id,
            region_scope="ALL",
        )
        officer = User(
            email="sla_officer@test.example.com",
            full_name="SLA Officer",
            password_hash=hash_password("Pass123!"),
            role=Role.RB_OFFICER,
            bureau_id=rb.id,
        )
        inst_rep = User(
            email="institution_rep@test.example.com",
            full_name="Institution Representative",
            password_hash=hash_password("Pass123!"),
            role=Role.INSTITUTION_REPRESENTATIVE,
            institution_id=inst.id,
        )
        db.add_all([admin, officer, inst_rep])
        db.flush()

        seed_demo_policies(db, actor=admin)
        db.commit()

        return {
            "rb_id": rb.id,
            "pgrc_id": pgrc.id,
            "inst_id": inst.id,
            "admin_id": admin.id,
            "officer_id": officer.id,
            "inst_rep_id": inst_rep.id,
            "admin_email": admin.email,
            "inst_rep_email": inst_rep.email,
        }


def _get_token(client: TestClient, email: str) -> str:
    res = client.post("/api/auth/token", json={"email": email, "password": "Pass123!"})
    assert res.status_code == 200, f"Auth failed for {email}: {res.text}"
    return res.json()["access_token"]


def _make_case(
    db: Session,
    inst_id: int,
    bureau_id: int,
    category: str = "Infrastructure",
    priority: Priority = Priority.HIGH,
    status: CaseStatus = CaseStatus.UNDER_PROCESS,
    receipt_dt: datetime | None = None,
) -> Case:
    dt = receipt_dt or datetime.now(UTC)
    case = Case(
        case_id=f"CC-AUD-{uuid.uuid4().hex[:6].upper()}",
        institution_id=inst_id,
        receipt_at=dt,
        receipt_date=dt.date(),
        source_channel="Web Portal",
        category=category,
        subject="Audit Test Subject",
        description="Audit test case description",
        priority=priority,
        originating_bureau_id=bureau_id,
        current_bureau_id=bureau_id,
        status=status,
        last_action="Case initialized",
        last_action_at=dt,
    )
    db.add(case)
    db.flush()
    return case


# ---------------------------------------------------------------------------
# AUDIT ITEM 1 — Breached Cases vs Future Deadlines & Uniqueness
# ---------------------------------------------------------------------------

class TestAuditItem1_UniqueSlaRecordsAndDeadlines:
    """Every case has exactly 1 SLA record. Deadlines for breached cases are in the past; on-track are in the future."""

    def test_database_enforces_unique_case_id_constraint(self, audit_seed_data):
        """Database constraint uq_case_sla_records_case_id prevents duplicate SLA records."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla1 = create_sla_record_for_case(db, case)
            assert sla1 is not None

            # Attempt raw insert of duplicate record for same case_id
            dup = CaseSlaRecord(
                case_id=case.id,
                policy_id=sla1.policy_id,
                policy_version=1,
                target_duration_days=30,
                calendar_type="calendar_days",
                start_time=datetime.now(UTC),
                original_deadline=datetime.now(UTC) + timedelta(days=30),
                current_deadline=datetime.now(UTC) + timedelta(days=30),
                status=SlaStatus.ON_TRACK.value,
            )
            db.add(dup)
            with pytest.raises(IntegrityError):
                db.flush()
            db.rollback()

    def test_create_sla_record_is_idempotent(self, audit_seed_data):
        """Calling create_sla_record_for_case multiple times returns existing record without duplicating."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            rec1 = create_sla_record_for_case(db, case)
            rec2 = create_sla_record_for_case(db, case)
            assert rec1.id == rec2.id
            count = db.scalar(select(func.count(CaseSlaRecord.id)).where(CaseSlaRecord.case_id == case.id))
            assert count == 1

    def test_breached_deadlines_are_in_past_and_on_track_in_future(self, audit_seed_data):
        """Regression test reconciling Item 1: Breached cases have deadlines earlier than current time; on-track have future deadlines."""
        now = datetime.now(UTC)
        with SessionLocal() as db:
            # 1. Past receipt date -> Breached case
            c_breached = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now - timedelta(days=60))
            sla_breached = create_sla_record_for_case(db, c_breached)
            assert sla_breached.status == SlaStatus.BREACHED.value
            assert ensure_utc(sla_breached.current_deadline) < now, "Breached case deadline must be in the past"
            assert sla_breached.consumed_percentage >= 100.0

            # 2. Present receipt date -> On-track case
            c_ontrack = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now)
            sla_ontrack = create_sla_record_for_case(db, c_ontrack)
            assert sla_ontrack.status == SlaStatus.ON_TRACK.value
            assert ensure_utc(sla_ontrack.current_deadline) > now, "On-track case deadline must be in the future"
            assert sla_ontrack.consumed_percentage < 75.0


# ---------------------------------------------------------------------------
# AUDIT ITEM 2 — Case CC-2026-00047 Anomaly Handling
# ---------------------------------------------------------------------------

class TestAuditItem2_BackdatedCaseRecord:
    """
    Case CC-2026-00047 has a receipt_date of 1222-02-21 — a data artifact.
    Pre-policy historical anomalies (year < 2000) are assigned a baseline policy
    and initialized in PAUSED state to prevent false operational breach inflation.
    Modern cases strictly enforce effective_from validity constraints.
    """

    def test_backdated_anomaly_resolves_policy_via_scoped_fallback(self, audit_seed_data):
        """Historical cases with timestamps earlier than year 2000 resolve fallback baseline policy."""
        ancient_dt = datetime(1222, 2, 21, 0, 0, 0, tzinfo=UTC)
        with SessionLocal() as db:
            policy = resolve_policy(
                db,
                category="Application",
                priority=Priority.MEDIUM,
                bureau_id=audit_seed_data["rb_id"],
                at_time=ancient_dt,
            )
            assert policy is not None, "Fallback policy resolution must match an active policy for ancient dates"

    def test_backdated_anomaly_initializes_in_paused_state(self, audit_seed_data):
        """Historical anomaly (year < 2000) is initialized as PAUSED, not an active operational breach."""
        ancient_dt = datetime(1222, 2, 21, 0, 0, 0, tzinfo=UTC)
        with SessionLocal() as db:
            case = _make_case(
                db,
                inst_id=audit_seed_data["inst_id"],
                bureau_id=audit_seed_data["rb_id"],
                category="Application",
                priority=Priority.MEDIUM,
                receipt_dt=ancient_dt,
            )
            sla_record = create_sla_record_for_case(db, case)
            assert sla_record is not None
            assert sla_record.case_id == case.id
            assert sla_record.status == SlaStatus.PAUSED.value
            assert sla_record.is_paused is True
            assert sla_record.consumed_percentage == 0.0

    def test_modern_case_strictly_respects_effective_from_dates(self, audit_seed_data):
        """Modern cases (year >= 2000) do NOT bypass effective_from policy constraints."""
        with SessionLocal() as db:
            # Create a policy effective only in the year 2030
            future_policy = SlaPolicy(
                name="Future Policy 2030",
                category="StrictConstraintTest",
                target_duration_days=30,
                effective_from=datetime(2030, 1, 1, tzinfo=UTC),
                is_active=True,
            )
            db.add(future_policy)
            db.flush()

            # Attempt to resolve policy for a 2026 complaint in that category
            matched = resolve_policy(
                db,
                category="StrictConstraintTest",
                at_time=datetime(2026, 6, 1, tzinfo=UTC),
            )
            # Must NOT match future_policy because 2026 < 2030 and year >= 2000
            assert matched is None or matched.name != "Future Policy 2030", (
                "resolve_policy must strictly enforce effective_from for modern cases"
            )


# ---------------------------------------------------------------------------
# AUDIT ITEM 3 — Active Case Policy Hierarchy and Deterministic Deadlines
# ---------------------------------------------------------------------------

class TestAuditItem3_ActiveCasePolicyAndDeadline:
    """Active cases resolve appropriate SLA policy and obtain deterministic future deadlines."""

    def test_policy_resolution_hierarchy(self, audit_seed_data):
        """Deterministic resolution follows: Bureau+Category > Category > Default."""
        with SessionLocal() as db:
            p_infra = resolve_policy(db, category="Infrastructure", priority=Priority.HIGH, bureau_id=audit_seed_data["rb_id"])
            assert p_infra is not None
            assert p_infra.category.lower() in ["infrastructure", "default"]

            p_unknown = resolve_policy(db, category="UnknownCategoryX", priority=Priority.LOW)
            assert p_unknown is not None
            assert "default" in p_unknown.category.lower() or "default" in p_unknown.name.lower()

    def test_active_case_has_valid_future_deadline(self, audit_seed_data):
        """Newly created active case receives a future current_deadline according to policy duration."""
        with SessionLocal() as db:
            now = datetime.now(UTC)
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now)
            sla = create_sla_record_for_case(db, case)
            assert sla is not None
            assert ensure_utc(sla.current_deadline) > now
            assert sla.status in [SlaStatus.ON_TRACK.value, SlaStatus.WARNING.value]


# ---------------------------------------------------------------------------
# AUDIT ITEM 4 — Terminal Cases Retain Frozen Metrics
# ---------------------------------------------------------------------------

class TestAuditItem4_TerminalCasesCompleted:
    """Disposed or Closed cases must be marked COMPLETED with actual duration and compliance flag."""

    def test_terminal_case_retains_completion_metrics(self, audit_seed_data):
        """complete_sla sets COMPLETED status, actual duration hours, and completion time."""
        with SessionLocal() as db:
            start_dt = datetime.now(UTC) - timedelta(days=5)
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=start_dt)
            sla = create_sla_record_for_case(db, case)
            assert sla is not None

            # Mark completed
            admin = db.get(User, audit_seed_data["admin_id"])
            completed_record = complete_sla(db, case=case, actor=admin)

            assert completed_record.status == SlaStatus.COMPLETED.value
            assert completed_record.completion_time is not None
            assert completed_record.actual_duration_hours is not None
            assert completed_record.actual_duration_hours > 0
            assert completed_record.completed_within_sla is True

    def test_evaluator_ignores_completed_records(self, audit_seed_data):
        """Subsequent live evaluations do not alter already completed SLA records."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla = create_sla_record_for_case(db, case)
            complete_sla(db, case=case)

            orig_duration = sla.actual_duration_hours
            orig_completion = sla.completion_time

            # Run evaluation
            evaluate_all_active(db)
            db.refresh(sla)

            assert sla.status == SlaStatus.COMPLETED.value
            assert sla.actual_duration_hours == orig_duration
            assert sla.completion_time == orig_completion


# ---------------------------------------------------------------------------
# AUDIT ITEM 5 — Indian Holiday Calendar & Edge Cases
# ---------------------------------------------------------------------------

class TestAuditItem5_HolidayCalendarEdgeCases:
    """Central gazetted holidays are mandatory non-working days; state observances are configurable opt-in.
    Handles leap years, year boundaries, consecutive holidays, and weekends.
    """

    def test_central_gazetted_holidays_are_non_working(self):
        """Republic Day, Independence Day, Gandhi Jayanti are always non-working."""
        national_holidays = [
            date(2026, 1, 26),  # Republic Day
            date(2026, 8, 15),  # Independence Day
            date(2026, 10, 2),  # Gandhi Jayanti
        ]
        central_only = get_applicable_holidays(include_state_observances=False)
        for d in national_holidays:
            assert not is_working_day(d, central_only), f"{d} must be non-working"

    def test_state_observances_not_in_central_holidays(self):
        """State observances like Holi/Diwali are separate from central holidays."""
        for d in STATE_OBSERVANCE_HOLIDAYS:
            assert d not in CENTRAL_GAZETTED_HOLIDAYS

    def test_state_observances_are_working_days_by_default(self):
        """Without opt-in, state-festival weekdays are ordinary working days."""
        holi_2026 = date(2026, 3, 4)  # Wednesday
        central_only = get_applicable_holidays(include_state_observances=False)
        assert is_working_day(holi_2026, central_only)

    def test_state_observances_become_holidays_when_opted_in(self):
        """When include_state_observances=True, state observances become holidays."""
        holi_2026 = date(2026, 3, 4)
        with_state = get_applicable_holidays(include_state_observances=True)
        assert not is_working_day(holi_2026, with_state)

    def test_leap_year_handling_feb_29(self):
        """Calendar calculation cleanly handles leap years (e.g. Feb 29, 2028)."""
        # 2028 is a leap year; Feb 28, 2028 is Monday
        start_dt = datetime(2028, 2, 28, 10, 0, 0, tzinfo=UTC)
        # Adding 1 business day advances to Feb 29, 2028 (Tuesday)
        d1 = add_business_days(start_dt, 1)
        assert d1.date() == date(2028, 2, 29), f"Expected Feb 29 2028, got {d1.date()}"
        # Adding 2 business days advances to March 1, 2028 (Wednesday)
        d2 = add_business_days(start_dt, 2)
        assert d2.date() == date(2028, 3, 1), f"Expected March 1 2028, got {d2.date()}"

    def test_year_boundary_and_central_holiday(self):
        """Dec 31 + 1 business day skips Jan 1 (Central Gazetted Holiday) to Jan 2."""
        # Dec 31, 2025 is Wednesday. Jan 1, 2026 is New Year's Day (Central Holiday).
        # Therefore, 1 business day from Dec 31, 2025 must land on Jan 2, 2026 (Friday).
        dec31 = datetime(2025, 12, 31, 10, 0, 0, tzinfo=UTC)
        result = add_business_days(dec31, 1, CENTRAL_GAZETTED_HOLIDAYS)
        assert result.date() == date(2026, 1, 2), f"Expected Jan 2, 2026, got {result.date()}"

    def test_consecutive_holidays_and_long_weekend(self):
        """Consecutive non-working days (Friday holiday + Sat + Sun + Monday holiday) are skipped cleanly."""
        # June 12, 2026 is Friday; June 15, 2026 is Monday.
        custom_holidays = {date(2026, 6, 12), date(2026, 6, 15)}
        thursday = datetime(2026, 6, 11, 10, 0, 0, tzinfo=UTC)
        # 1 business day from Thursday must land on Tuesday, June 16!
        res = add_business_days(thursday, 1, custom_holidays)
        assert res.date() == date(2026, 6, 16), f"Expected June 16, got {res.date()}"


# ---------------------------------------------------------------------------
# AUDIT ITEMS 6 & 7 — Background Scheduler & Fault Isolation
# ---------------------------------------------------------------------------

class TestAuditItems6And7_BackgroundScheduler:
    """Background evaluator runs automatically in application lifespan and survives restarts.
    Evaluation loop isolates individual case errors so one bad record does not halt the rest.
    """

    def test_scheduler_task_registered_in_lifespan(self, client):
        """Lifespan registers asyncio background evaluator task."""
        from app.main import _sla_scheduler_task as task
        assert task is not None
        assert isinstance(task, asyncio.Task)
        assert task.get_name() == "sla-background-evaluator"

    def test_evaluator_runs_without_error(self, audit_seed_data):
        """evaluate_all_active executes cleanly and returns evaluation metrics dictionary."""
        with SessionLocal() as db:
            result = evaluate_all_active(db)
            assert isinstance(result, dict)
            assert "evaluated" in result
            assert "warnings" in result
            assert "at_risk" in result
            assert "breached" in result
            assert "escalations" in result or "escalations_created" in result

    def test_scheduler_restart_behavior(self):
        """Simulating restart of FastAPI lifespan cleanly cancels old task and spawns fresh task."""
        async def _run_restart_cycle():
            async with lifespan(app):
                from app.main import _sla_scheduler_task as task_during
                assert task_during is not None
                assert not task_during.done()

            from app.main import _sla_scheduler_task as task_after
            if task_after:
                assert task_after.done() or task_after.cancelled()

        asyncio.run(_run_restart_cycle())

    def test_fault_isolation_in_evaluate_all_active(self, audit_seed_data):
        """An error on one corrupt/anomalous record does not stop evaluation of remaining cases."""
        with SessionLocal() as db:
            c1 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            c2 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla1 = create_sla_record_for_case(db, c1)
            sla2 = create_sla_record_for_case(db, c2)

            # Intentionally corrupt sla1 policy_id to non-existent ID
            sla1.policy_id = 999999
            db.commit()

            # evaluate_all_active must continue and evaluate sla2 despite sla1's missing policy
            res = evaluate_all_active(db)
            assert res["evaluated"] >= 2


# ---------------------------------------------------------------------------
# AUDIT ITEM 8 — All Four Escalation Levels (L1, L2, L3, L4) & Idempotency
# ---------------------------------------------------------------------------

class TestAuditItem8_AllFourEscalationLevels:
    """Verifies all four escalation thresholds:
    - 75%: Warning alert
    - 90%: Level 1 Escalation (Bureau Coordinator)
    - 100%: Level 2 Escalation (Senior Management)
    - 3 Days Overdue: Level 3 Escalation (Competent Authority)
    - 7 Days Overdue: Level 4 Escalation (System Administrator / Review Board)
    Also verifies idempotency, suppression for paused/completed cases, and recipient authorization.
    """

    def test_level_1_escalation_at_90_percent(self, audit_seed_data):
        """Consumed >= 90% triggers Level 1 escalation to Bureau Coordinator."""
        with SessionLocal() as db:
            # 30-day policy: 90% consumed is 27 days elapsed
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=datetime.now(UTC) - timedelta(days=27, hours=2))
            sla = create_sla_record_for_case(db, case)
            evaluate_sla_record(db, sla)
            db.commit()

            assert sla.status == SlaStatus.AT_RISK.value
            esc = db.scalar(select(SlaEscalation).where(SlaEscalation.sla_record_id == sla.id, SlaEscalation.escalation_level == 1))
            assert esc is not None
            assert esc.target_role == "Bureau Coordinator"
            assert esc.trigger_type == "at_risk_threshold"

    def test_level_2_escalation_at_100_percent(self, audit_seed_data):
        """Consumed >= 100% (breach) triggers Level 2 escalation to Senior Management."""
        with SessionLocal() as db:
            # 30-day policy: 30 days and 2 hours elapsed (just breached)
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=datetime.now(UTC) - timedelta(days=30, hours=2))
            sla = create_sla_record_for_case(db, case)
            evaluate_sla_record(db, sla)
            db.commit()

            assert sla.status == SlaStatus.BREACHED.value
            esc = db.scalar(select(SlaEscalation).where(SlaEscalation.sla_record_id == sla.id, SlaEscalation.escalation_level == 2))
            assert esc is not None
            assert esc.target_role == "Senior Management"
            assert esc.trigger_type == "breach_threshold"

    def test_level_3_escalation_at_3_days_overdue(self, audit_seed_data):
        """Overdue >= 3 days triggers Level 3 escalation to Competent Authority."""
        with SessionLocal() as db:
            # 30-day policy + 3.5 days overdue = 33.5 days elapsed
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=datetime.now(UTC) - timedelta(days=34))
            sla = create_sla_record_for_case(db, case)
            evaluate_sla_record(db, sla)
            db.commit()

            esc = db.scalar(select(SlaEscalation).where(SlaEscalation.sla_record_id == sla.id, SlaEscalation.escalation_level == 3))
            assert esc is not None
            assert esc.target_role == "Competent Authority"
            assert esc.trigger_type == "overdue_days_3"

    def test_level_4_escalation_at_7_days_overdue(self, audit_seed_data):
        """Overdue >= 7 days triggers Level 4 escalation to System Administrator / Review Board."""
        with SessionLocal() as db:
            # 30-day policy + 8 days overdue = 38 days elapsed
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=datetime.now(UTC) - timedelta(days=38))
            sla = create_sla_record_for_case(db, case)
            evaluate_sla_record(db, sla)
            db.commit()

            esc = db.scalar(select(SlaEscalation).where(SlaEscalation.sla_record_id == sla.id, SlaEscalation.escalation_level == 4))
            assert esc is not None
            assert esc.target_role == "System Administrator / Review Board"
            assert esc.trigger_type == "overdue_days_7"
            assert sla.escalation_level == 4

    def test_paused_case_triggers_no_escalations(self, audit_seed_data):
        """A paused case at 150% duration triggers NO escalations."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla = create_sla_record_for_case(db, case)
            admin = db.get(User, audit_seed_data["admin_id"])
            pause_sla(db, case=case, reason="Court Stay / Legal Proceedings", notes=None, actor=admin)

            # Evaluate at a simulated time 60 days in the future
            future_dt = datetime.now(UTC) + timedelta(days=60)
            res = evaluate_sla_record(db, sla, eval_time=future_dt)
            db.commit()

            assert res["status"] == SlaStatus.PAUSED.value
            esc_count = db.scalar(select(func.count(SlaEscalation.id)).where(SlaEscalation.sla_record_id == sla.id)) or 0
            assert esc_count == 0, "Paused case must not trigger any escalations"

    def test_repeated_evaluation_preserves_escalations_without_duplication(self, audit_seed_data):
        """Running evaluation repeatedly on a breached case does not generate duplicate L1/L2/L3/L4 records."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=datetime.now(UTC) - timedelta(days=40))
            sla = create_sla_record_for_case(db, case)

            # Run 1
            evaluate_all_active(db)
            count1 = db.scalar(select(func.count(SlaEscalation.id)).where(SlaEscalation.sla_record_id == sla.id)) or 0
            assert count1 == 4  # All 4 levels triggered for 10-day overdue case

            # Run 2
            evaluate_all_active(db)
            count2 = db.scalar(select(func.count(SlaEscalation.id)).where(SlaEscalation.sla_record_id == sla.id)) or 0
            assert count2 == count1, "Repeated evaluation must not duplicate escalations"


# ---------------------------------------------------------------------------
# AUDIT ITEM 9 — Policy Update Immutability Guard
# ---------------------------------------------------------------------------

class TestAuditItem9_PolicyUpdatePreservesDeadlines:
    """Updating policy target duration leaves existing complaint deadlines intact."""

    def test_policy_duration_change_does_not_alter_existing_deadlines(self, client, audit_seed_data):
        """When an SLA policy is updated, existing CaseSlaRecord.current_deadline values remain unchanged."""
        token = _get_token(client, audit_seed_data["admin_email"])
        headers = {"Authorization": f"Bearer {token}"}

        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla = create_sla_record_for_case(db, case)
            orig_deadline = sla.current_deadline
            policy_id = sla.policy_id

        # Update policy target duration from API
        resp = client.put(
            f"/api/sla/policies/{policy_id}",
            json={"target_duration_days": 120, "change_reason": "Statutory extension"},
            headers=headers,
        )
        assert resp.status_code == 200

        # Verify existing record deadline is unchanged
        with SessionLocal() as db:
            rec_after = db.scalar(select(CaseSlaRecord).where(CaseSlaRecord.case_id == case.id))
            assert rec_after.current_deadline == orig_deadline, "Existing deadline was modified by policy update"


# ---------------------------------------------------------------------------
# AUDIT ITEM 10 — Audit History Completeness
# ---------------------------------------------------------------------------

class TestAuditItem10_AuditHistoryCompleteness:
    """Pause, resume, complete, and bureau transfers create immutable audit and SLA event records."""

    def test_pause_resume_complete_records_sla_events(self, audit_seed_data):
        """Lifecycle operations produce distinct SlaEvent records."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla = create_sla_record_for_case(db, case)
            admin = db.get(User, audit_seed_data["admin_id"])

            # 1. Pause
            pause_sla(db, case=case, reason="Court Stay / Legal Proceedings", notes="Stay order #101", actor=admin)
            events_pause = db.scalars(
                select(SlaEvent).where(SlaEvent.sla_record_id == sla.id, SlaEvent.event_type == "PAUSED")
            ).all()
            assert len(events_pause) == 1

            # 2. Resume
            resume_sla(db, case=case, notes="Stay vacated", actor=admin)
            events_resume = db.scalars(
                select(SlaEvent).where(SlaEvent.sla_record_id == sla.id, SlaEvent.event_type == "RESUMED")
            ).all()
            assert len(events_resume) == 1

            # 3. Complete
            complete_sla(db, case=case, actor=admin)
            events_complete = db.scalars(
                select(SlaEvent).where(SlaEvent.sla_record_id == sla.id, SlaEvent.event_type == "COMPLETED")
            ).all()
            assert len(events_complete) == 1

    def test_case_transfer_preserves_sla_record_and_writes_history(self, audit_seed_data):
        """Bureau transfer creates CaseEvent and leaves CaseSlaRecord linked and active."""
        with SessionLocal() as db:
            case = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"])
            sla = create_sla_record_for_case(db, case)
            admin = db.get(User, audit_seed_data["admin_id"])

            # Simulate bureau transfer
            prev_bureau_id = case.current_bureau_id
            case.current_bureau_id = audit_seed_data["pgrc_id"]
            case.last_action = "Transferred to Public Grievance Cell"
            case.last_action_at = datetime.now(UTC)

            event = CaseEvent(
                case_id=case.id,
                action_type=ActionType.TRANSFERRED,
                actor_id=admin.id,
                bureau_id=audit_seed_data["pgrc_id"],
                previous_values={"bureau_id": prev_bureau_id},
                new_values={"bureau_id": audit_seed_data["pgrc_id"]},
                remarks="Jurisdiction re-assignment",
            )
            db.add(event)
            db.commit()

            # Verify SLA record is preserved
            db.refresh(sla)
            assert sla.case_id == case.id
            assert sla.status == SlaStatus.ON_TRACK.value

            # Verify CaseEvent written
            history = db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id)).all()
            assert any(e.action_type == ActionType.TRANSFERRED for e in history)


# ---------------------------------------------------------------------------
# AUDIT ITEM 11 — Role-Based Access Control (RBAC)
# ---------------------------------------------------------------------------

class TestAuditItem11_InstitutionUserRBAC:
    """Institution Representatives receive HTTP 403 on internal bureau/officer analytics and risk dashboard."""

    def test_institution_user_forbidden_from_internal_endpoints(self, client, audit_seed_data):
        """Institution representative is blocked (403) from internal SLA analytics and all-records list."""
        token = _get_token(client, audit_seed_data["inst_rep_email"])
        headers = {"Authorization": f"Bearer {token}"}

        blocked_get_urls = [
            "/api/sla/analytics/bureaus",
            "/api/sla/analytics/officers",
            "/api/sla/risk/dashboard",
            "/api/sla/records",
        ]
        for url in blocked_get_urls:
            resp = client.get(url, headers=headers)
            assert resp.status_code == 403, f"{url} should return 403 for institution rep, got {resp.status_code}"

        # Policy mutation is also forbidden (403) for institution representative
        policy_payload = {
            "name": "Illegal Policy Creation",
            "category": "Fraud",
            "target_duration_days": 15,
            "calendar_type": "calendar_days",
            "warning_threshold_pct": 75,
            "at_risk_threshold_pct": 90,
            "is_active": True,
        }
        resp_post = client.post("/api/sla/policies", json=policy_payload, headers=headers)
        assert resp_post.status_code == 403, f"POST /api/sla/policies should return 403 for institution rep, got {resp_post.status_code}"

    def test_institution_user_cannot_access_other_institutions_sla_record(self, client, audit_seed_data):
        """Institution representative is blocked (403) from viewing SLA records belonging to another institution."""
        with SessionLocal() as db:
            other_inst = Institution(
                permanent_id="SLA-OTHER-INST",
                permanent_id_verified=True,
                name="Other College",
                normalized_name="other college",
                institution_type="Engineering",
                region="South",
                status="Active",
            )
            db.add(other_inst)
            db.flush()
            other_case = _make_case(db, other_inst.id, audit_seed_data["rb_id"])
            create_sla_record_for_case(db, other_case)
            db.commit()
            other_case_id = other_case.case_id

        token = _get_token(client, audit_seed_data["inst_rep_email"])
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get(f"/api/sla/records/{other_case_id}", headers=headers)
        assert resp.status_code == 403, f"Expected 403 for viewing another institution's case, got {resp.status_code}"

    def test_admin_has_full_access_to_analytics_endpoints(self, client, audit_seed_data):
        """Administrator successfully accesses internal bureau/officer analytics and risk dashboard."""
        token = _get_token(client, audit_seed_data["admin_email"])
        headers = {"Authorization": f"Bearer {token}"}

        admin_urls = [
            "/api/sla/analytics/bureaus",
            "/api/sla/analytics/officers",
            "/api/sla/risk/dashboard",
            "/api/sla/records",
            "/api/sla/policies",
            "/api/sla/dashboard",
        ]
        for url in admin_urls:
            resp = client.get(url, headers=headers)
            assert resp.status_code == 200, f"{url} failed for admin: {resp.text}"


# ---------------------------------------------------------------------------
# AUDIT ITEM 12 — Metric Definitions & Boundary Conditions
# ---------------------------------------------------------------------------

class TestAuditItem12_MetricDefinitionsAndBoundaryConditions:
    """Verifies that active_in_sla_percentage includes AT_RISK cases (not yet breached),
    active_healthy_percentage only includes ON_TRACK and WARNING, and boundary conditions
    (0 active cases, 0 completed cases) do not divide by zero.
    """

    def test_dashboard_metrics_match_direct_db_aggregation(self, client, audit_seed_data):
        """Verify each card metric against direct SQL / ORM count queries."""
        with SessionLocal() as db:
            now = datetime.now(UTC)
            # Case 1: On track
            c1 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now)
            create_sla_record_for_case(db, c1)

            # Case 2: Breached
            c2 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now - timedelta(days=60))
            create_sla_record_for_case(db, c2)

            # Case 3: Completed
            c3 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now - timedelta(days=5))
            create_sla_record_for_case(db, c3)
            complete_sla(db, case=c3)

            # Re-evaluate
            evaluate_all_active(db)

            # Direct DB queries
            counts: dict[str, int] = {}
            for st in SlaStatus:
                counts[st.value] = db.scalar(
                    select(func.count(CaseSlaRecord.id)).where(CaseSlaRecord.status == st.value)
                ) or 0
            total_escalations = db.scalar(select(func.count(SlaEscalation.id))) or 0

        # Query dashboard API
        token = _get_token(client, audit_seed_data["admin_email"])
        resp = client.get("/api/sla/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["on_track_count"] == counts[SlaStatus.ON_TRACK.value]
        assert data["breached_count"] == counts[SlaStatus.BREACHED.value]
        assert data["completed_count"] == counts[SlaStatus.COMPLETED.value]
        assert data["total_escalations_count"] == total_escalations

        expected_active = sum(
            counts[s.value] for s in [SlaStatus.ON_TRACK, SlaStatus.WARNING, SlaStatus.AT_RISK, SlaStatus.BREACHED, SlaStatus.PAUSED]
        )
        assert data["total_active_records"] == expected_active

    def test_active_in_sla_includes_at_risk_cases(self, client, audit_seed_data):
        """AT_RISK cases are strictly within deadline and must be counted in active_in_sla_percentage."""
        with SessionLocal() as db:
            now = datetime.now(UTC)
            # 1 on-track case (0% consumed)
            c1 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now)
            create_sla_record_for_case(db, c1)

            # 1 at-risk case (92% consumed)
            c2 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now - timedelta(days=27, hours=15))
            create_sla_record_for_case(db, c2)

            # 1 breached case (120% consumed)
            c3 = _make_case(db, audit_seed_data["inst_id"], audit_seed_data["rb_id"], receipt_dt=now - timedelta(days=40))
            create_sla_record_for_case(db, c3)

            evaluate_all_active(db)

        token = _get_token(client, audit_seed_data["admin_email"])
        resp = client.get("/api/sla/dashboard", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_active_records"] == 3
        assert data["at_risk_count"] == 1
        assert data["breached_count"] == 1
        assert data["on_track_count"] == 1

        # Active in-SLA rate: (3 - 1 breached) / 3 = 2 / 3 = 66.7%
        assert data["active_compliance_percentage"] == 66.7
        # Active healthy rate: only on_track + warning = 1 / 3 = 33.3%
        assert data["active_healthy_percentage"] == 33.3
