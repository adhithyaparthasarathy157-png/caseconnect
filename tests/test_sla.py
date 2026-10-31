"""Comprehensive tests for the SLA & Pendency Intelligence Engine."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.enums import CaseStatus, Priority, Role, SlaCalendarType, SlaStatus
from app.main import app
from app.models import Bureau, Case, CaseSlaRecord, Institution, SlaPolicy, SlaPolicyVersion, User
from app.security import hash_password
from app.sla.calendar import (
    add_business_days,
    add_calendar_days,
    calculate_deadline,
    is_working_day,
)
from app.sla.evaluator import evaluate_all_active
from app.sla.policy_engine import (
    resolve_policy,
    seed_demo_policies,
)
from app.sla.risk import evaluate_case_pendency_risk


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sla_setup_data():
    with SessionLocal() as db:
        rb = Bureau(code="RB", name="Regulation Bureau")
        pgrc = Bureau(code="PGRC", name="Public Grievance")
        db.add_all([rb, pgrc])
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
        pgrc_officer = User(
            email="pgrc_officer@test.example.com",
            full_name="PGRC Officer",
            password_hash=hash_password("Pass123!"),
            role=Role.PGRC_OFFICER,
            bureau_id=pgrc.id,
        )
        db.add_all([admin, officer, pgrc_officer])

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
        db.commit()

        # Seed demo policies
        seed_demo_policies(db, actor=admin)
        db.commit()

        return {
            "rb_id": rb.id,
            "pgrc_id": pgrc.id,
            "admin_email": admin.email,
            "officer_email": officer.email,
            "officer_id": officer.id,
            "pgrc_officer_email": pgrc_officer.email,
            "institution_id": inst.id,
        }


def get_auth_token(client: TestClient, email: str) -> dict[str, str]:
    res = client.post("/api/auth/token", json={"email": email, "password": "Pass123!"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


# ---------------------------------------------------------------------------
# 1. Calendar & Working Day Unit Tests
# ---------------------------------------------------------------------------

def test_working_day_and_holidays():
    saturday = date(2026, 11, 7)  # Saturday
    sunday = date(2026, 11, 8)    # Sunday
    monday = date(2026, 11, 9)    # Monday
    assert not is_working_day(saturday)
    assert not is_working_day(sunday)
    assert is_working_day(monday)

    # Republic Day is a statutory holiday
    republic_day = date(2026, 1, 26)
    assert not is_working_day(republic_day)


def test_deadline_calculations():
    start = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)  # Monday
    # 5 calendar days -> Nov 7 (Saturday)
    cal_dl = add_calendar_days(start, 5)
    assert cal_dl.day == 7

    # 5 business days starting Mon Nov 2 -> Mon Nov 9 (skips Sat Nov 7 & Sun Nov 8)
    biz_dl = add_business_days(start, 5)
    assert biz_dl.day == 9


# ---------------------------------------------------------------------------
# 2. Deterministic Policy Resolution Hierarchy
# ---------------------------------------------------------------------------

def test_policy_resolution_hierarchy(sla_setup_data):
    with SessionLocal() as db:
        rb_id = sla_setup_data["rb_id"]

        # Stage 1: Exact match (Category + Priority + Bureau)
        exact_pol = SlaPolicy(
            name="Exact Grievance High RB",
            category="Grievance",
            priority=Priority.HIGH,
            bureau_id=rb_id,
            target_duration_days=10,
            calendar_type=SlaCalendarType.CALENDAR_DAYS,
            warning_threshold_pct=75.0,
            at_risk_threshold_pct=90.0,
            is_active=True,
            version=1,
            effective_from=datetime(2020, 1, 1, tzinfo=UTC),
        )
        db.add(exact_pol)
        db.commit()

        resolved = resolve_policy(db, category="Grievance", priority="High", bureau_id=rb_id)
        assert resolved is not None
        assert resolved.name == "Exact Grievance High RB"

        # Stage 2: Category + Priority fallback
        resolved_diff_bureau = resolve_policy(db, category="Grievance", priority="Critical", bureau_id=99999)
        assert resolved_diff_bureau is not None

        # Fallback to default
        resolved_default = resolve_policy(db, category="UnknownCategory123", priority="Low", bureau_id=99999)
        assert resolved_default is not None
        assert "Default" in resolved_default.name or resolved_default.category == "Default"


# ---------------------------------------------------------------------------
# 3. Policy CRUD & Versioning
# ---------------------------------------------------------------------------

def test_policy_creation_and_versioning(client, sla_setup_data):
    admin_auth = get_auth_token(client, sla_setup_data["admin_email"])

    # Create a new policy
    payload = {
        "name": "Custom Student Safety SLA",
        "description": "Specific timeline for campus safety issues",
        "category": "Safety",
        "priority": "Critical",
        "target_duration_days": 7,
        "calendar_type": "calendar_days",
        "warning_threshold_pct": 70.0,
        "at_risk_threshold_pct": 85.0,
        "is_active": True,
    }
    create_res = client.post("/api/sla/policies", json=payload, headers=admin_auth)
    assert create_res.status_code == 201, create_res.text
    created = create_res.json()
    policy_id = created["id"]
    assert created["version"] == 1

    # Update the policy -> version should bump to 2 and version snapshot created
    update_payload = {
        "name": "Custom Student Safety SLA - Revised",
        "target_duration_days": 5,
        "change_reason": "Executive directive for faster student safety resolution",
    }
    update_res = client.put(f"/api/sla/policies/{policy_id}", json=update_payload, headers=admin_auth)
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["version"] == 2
    assert updated["target_duration_days"] == 5

    # Check version history
    versions_res = client.get(f"/api/sla/policies/{policy_id}/versions", headers=admin_auth)
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) >= 1
    # Historical snapshot of version 1
    v1 = next((v for v in versions if v["version"] == 1), None)
    assert v1 is not None
    assert v1["snapshot"]["target_duration_days"] == 7


# ---------------------------------------------------------------------------
# 4. Automatic SLA Record Creation on Case Submission
# ---------------------------------------------------------------------------

def test_case_creation_initializes_sla_record(client, sla_setup_data):
    admin_auth = get_auth_token(client, sla_setup_data["admin_email"])

    case_payload = {
        "institution_id": sla_setup_data["institution_id"],
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Portal",
        "category": "Grievance",
        "priority": "Critical",
        "subject": "Delayed exam results causing student distress",
        "description": "Detailed student grievance description regarding examination cell delays.",
        "originating_bureau_id": sla_setup_data["pgrc_id"],
        "current_bureau_id": sla_setup_data["pgrc_id"],
    }
    create_res = client.post("/api/cases", json=case_payload, headers=admin_auth)
    assert create_res.status_code == 201, create_res.text
    case_data = create_res.json()
    case_identifier = case_data["case_id"]

    # Retrieve SLA record
    sla_res = client.get(f"/api/sla/records/{case_identifier}", headers=admin_auth)
    assert sla_res.status_code == 200, sla_res.text
    sla_data = sla_res.json()
    assert sla_data["case_ref"] == case_identifier
    assert sla_data["status"] == "ON_TRACK"
    assert sla_data["target_duration_days"] > 0
    assert sla_data["current_deadline"] is not None


# ---------------------------------------------------------------------------
# 5. Pause & Resume SLA Lifecycle
# ---------------------------------------------------------------------------

def test_sla_pause_and_resume(client, sla_setup_data):
    admin_auth = get_auth_token(client, sla_setup_data["admin_email"])

    # Create case
    case_payload = {
        "institution_id": sla_setup_data["institution_id"],
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Portal",
        "category": "Grievance",
        "priority": "Medium",
        "subject": "Curriculum compliance inquiry",
        "description": "Inquiry regarding syllabus revision requirements.",
        "originating_bureau_id": sla_setup_data["rb_id"],
    }
    c_res = client.post("/api/cases", json=case_payload, headers=admin_auth)
    assert c_res.status_code == 201
    case_identifier = c_res.json()["case_id"]

    # Pause SLA
    pause_payload = {
        "reason": "Awaiting Institutional Clarification / Response",
        "notes": "Official clarification letter dispatched to college principal.",
    }
    pause_res = client.post(f"/api/sla/records/{case_identifier}/pause", json=pause_payload, headers=admin_auth)
    assert pause_res.status_code == 200, pause_res.text
    record = pause_res.json()
    assert record["status"] == "PAUSED"
    assert record["is_paused"] is True

    # Check pause history
    pauses_res = client.get(f"/api/sla/records/{case_identifier}/pauses", headers=admin_auth)
    assert pauses_res.status_code == 200
    pauses = pauses_res.json()
    assert len(pauses) == 1
    assert pauses[0]["pause_reason"] == "Awaiting Institutional Clarification / Response"

    # Resume SLA
    resume_payload = {
        "notes": "College submitted comprehensive clarification reply.",
    }
    resume_res = client.post(f"/api/sla/records/{case_identifier}/resume", json=resume_payload, headers=admin_auth)
    assert resume_res.status_code == 200
    resumed = resume_res.json()
    assert resumed["status"] == "ON_TRACK"
    assert resumed["is_paused"] is False


# ---------------------------------------------------------------------------
# 6. Terminal Status Completion Tracking
# ---------------------------------------------------------------------------

def test_terminal_case_disposal_completes_sla(client, sla_setup_data):
    admin_auth = get_auth_token(client, sla_setup_data["admin_email"])

    # Create case
    c_res = client.post("/api/cases", json={
        "institution_id": sla_setup_data["institution_id"],
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Portal",
        "category": "Approval",
        "priority": "Low",
        "subject": "Minor fee query",
        "description": "Student inquired about prospectus fee breakdown.",
        "originating_bureau_id": sla_setup_data["rb_id"],
    }, headers=admin_auth)
    assert c_res.status_code == 201
    case_identifier = c_res.json()["case_id"]

    # Transition to Under Process first, then Disposed
    client.patch(f"/api/cases/{case_identifier}", json={
        "status": "Under Review",
        "remarks": "In review",
    }, headers=admin_auth)
    client.patch(f"/api/cases/{case_identifier}", json={
        "status": "Under Process",
        "remarks": "Processing resolution",
    }, headers=admin_auth)
    update_res = client.patch(f"/api/cases/{case_identifier}", json={
        "status": "Disposed",
        "remarks": "Fee schedule explained and dispute resolved mutually.",
    }, headers=admin_auth)
    assert update_res.status_code == 200

    # Verify SLA status is COMPLETED
    sla_res = client.get(f"/api/sla/records/{case_identifier}", headers=admin_auth)
    assert sla_res.status_code == 200
    record = sla_res.json()
    assert record["status"] == "COMPLETED"
    assert record["completion_time"] is not None
    assert record["completed_within_sla"] is True


# ---------------------------------------------------------------------------
# 7. Automated Evaluator & Escalations
# ---------------------------------------------------------------------------

def test_evaluator_and_escalation_generation(client, sla_setup_data):
    with SessionLocal() as db:
        # Create an artificial case with a past deadline
        c = Case(
            case_id="CC-TEST-BREACH-001",
            institution_id=sla_setup_data["institution_id"],
            receipt_at=datetime.now(UTC) - timedelta(days=40),
            receipt_date=(datetime.now(UTC) - timedelta(days=40)).date(),
            source_channel="Portal",
            category="Infrastructure",
            priority=Priority.HIGH,
            status=CaseStatus.UNDER_PROCESS,
            subject="Dangerous laboratory ceiling cracks",
            description="Structural hazard reported in chemical laboratory.",
            originating_bureau_id=sla_setup_data["rb_id"],
            current_bureau_id=sla_setup_data["rb_id"],
            last_action="Under Process",
            last_action_at=datetime.now(UTC) - timedelta(days=40),
        )
        db.add(c)
        db.commit()

        policy = db.query(SlaPolicy).first()

        # Create breached SLA record
        past_deadline = datetime.now(UTC) - timedelta(days=5)
        sla_rec = CaseSlaRecord(
            case_id=c.id,
            case_ref=c.case_id,
            policy_id=policy.id,
            policy_version=1,
            target_duration_days=15,
            calendar_type=SlaCalendarType.CALENDAR_DAYS.value,
            start_time=datetime.now(UTC) - timedelta(days=20),
            original_deadline=past_deadline,
            current_deadline=past_deadline,
            status=SlaStatus.ON_TRACK.value,
        )
        db.add(sla_rec)
        db.commit()

        # Run evaluator
        res = evaluate_all_active(db)
        assert res["evaluated"] >= 1
        assert res["breached"] >= 1
        assert res["escalations"] >= 1

        db.refresh(sla_rec)
        assert sla_rec.status == SlaStatus.BREACHED.value

        # Test idempotency: running again should not duplicate escalations
        res2 = evaluate_all_active(db)
        assert res2["escalations"] == 0


# ---------------------------------------------------------------------------
# 8. RBAC Enforcements
# ---------------------------------------------------------------------------

def test_sla_rbac_rules(client, sla_setup_data):
    officer_auth = get_auth_token(client, sla_setup_data["officer_email"])

    # Normal officer cannot create an SLA policy
    payload = {
        "name": "Unauthorized Policy",
        "category": "Other",
        "target_duration_days": 10,
        "calendar_type": "calendar_days",
    }
    res = client.post("/api/sla/policies", json=payload, headers=officer_auth)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# 9. SLA Dashboard & Analytics
# ---------------------------------------------------------------------------

def test_sla_dashboard_and_analytics(client, sla_setup_data):
    admin_auth = get_auth_token(client, sla_setup_data["admin_email"])

    # KPI summary
    dash_res = client.get("/api/sla/dashboard", headers=admin_auth)
    assert dash_res.status_code == 200
    data = dash_res.json()
    assert "total_active_records" in data
    assert "on_track_count" in data
    assert "breached_count" in data
    assert "compliance_percentage" in data

    # Bureau metrics
    bureau_res = client.get("/api/sla/analytics/bureaus", headers=admin_auth)
    assert bureau_res.status_code == 200
    bureaus = bureau_res.json()
    assert isinstance(bureaus, list)

    # CSV Export
    csv_res = client.get("/api/sla/reports/export-csv", headers=admin_auth)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "Case ID,Institution,Category" in csv_res.text


# ---------------------------------------------------------------------------
# 10. AI Pendency Risk Intelligence
# ---------------------------------------------------------------------------

def test_ai_pendency_risk_assessment(sla_setup_data):
    with SessionLocal() as db:
        case = db.query(Case).filter(Case.case_id == "CC-TEST-BREACH-001").first()
        if not case:
            case = Case(
                case_id="CC-TEST-RISK-001",
                institution_id=sla_setup_data["institution_id"],
                receipt_at=datetime.now(UTC) - timedelta(days=30),
                receipt_date=(datetime.now(UTC) - timedelta(days=30)).date(),
                source_channel="Portal",
                category="Faculty",
                priority=Priority.CRITICAL,
                status=CaseStatus.UNDER_PROCESS,
                subject="Unlawful faculty mass termination",
                description="Institution arbitrarily terminated 15 engineering professors.",
                originating_bureau_id=sla_setup_data["rb_id"],
                current_bureau_id=sla_setup_data["rb_id"],
                last_action="Under Process",
                last_action_at=datetime.now(UTC) - timedelta(days=30),
            )
            db.add(case)
            db.commit()

        assessment = evaluate_case_pendency_risk(db, case)
        assert assessment.risk_score >= 0
        assert assessment.risk_score <= 100
        assert assessment.risk_level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert len(assessment.contributing_factors) >= 1
        assert assessment.recommended_action is not None
        assert len(assessment.recommended_action) > 0
