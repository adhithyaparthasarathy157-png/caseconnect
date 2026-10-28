"""Regression tests for Coordination, Overview Filters, Portal Navigation, and Institution Search."""
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.enums import AlertSeverity, CaseStatus, Role
from app.main import app
from app.models import Alert, Bureau, Case, Institution, OverlapCandidate, User
from app.security import hash_password
from app.services import normalize_name


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def setup_data():
    """Seed test institutions, bureaus, users, and cases in isolated test DB."""
    with SessionLocal() as db:
        rb = Bureau(code="RB", name="Regulation Bureau")
        apb = Bureau(code="APB", name="Approval Bureau")
        db.add_all([rb, apb])
        db.flush()

        inst1 = Institution(
            permanent_id="DEMO-AICTE-0001",
            permanent_id_verified=True,
            name="Alpha Engineering Institute",
            normalized_name=normalize_name("Alpha Engineering Institute"),
            institution_type="College",
            region="North",
            status="Active",
        )
        inst2 = Institution(
            permanent_id="DEMO-AICTE-0003",
            permanent_id_verified=False,
            name="Fictional East Institute of Technology 03",
            normalized_name=normalize_name("Fictional East Institute of Technology 03"),
            institution_type="University",
            region="East",
            status="Active",
        )
        db.add_all([inst1, inst2])
        db.flush()

        admin = User(
            email="admin@test.example.com",
            full_name="Admin User",
            password_hash=hash_password("Pass123!"),
            role=Role.ADMIN,
            is_active=True,
        )
        rep1 = User(
            email="rep1@test.example.com",
            full_name="Rep Alpha",
            password_hash=hash_password("Pass123!"),
            role=Role.INSTITUTION_REPRESENTATIVE,
            institution_id=inst1.id,
            bureau_id=rb.id,
            is_active=True,
        )
        db.add_all([admin, rep1])
        db.flush()

        # Case A: Inst 1, in RB (bureau 1)
        case_a = Case(
            case_id="CC-2026-90001",
            institution_id=inst1.id,
            originating_bureau_id=rb.id,
            current_bureau_id=rb.id,
            receipt_at=datetime(2026, 10, 1, 10, 0, tzinfo=UTC),
            receipt_date=date(2026, 10, 1),
            source_channel="Portal",
            category="Grievance",
            priority="Medium",
            subject="Alpha grievance report",
            description="Detail for Alpha grievance",
            status=CaseStatus.RECEIVED,
            last_action="Case created",
            last_action_at=datetime.now(UTC),
        )
        # Case B: Inst 1, in APB (bureau 2) -> different bureau from Case A!
        case_b = Case(
            case_id="CC-2026-90002",
            institution_id=inst1.id,
            originating_bureau_id=apb.id,
            current_bureau_id=apb.id,
            receipt_at=datetime(2026, 10, 5, 10, 0, tzinfo=UTC),
            receipt_date=date(2026, 10, 5),
            source_channel="Portal",
            category="Grievance",
            priority="High",
            subject="Alpha grievance duplicate candidate",
            description="Detail for Alpha duplicate",
            status=CaseStatus.UNDER_REVIEW,
            last_action="Under review",
            last_action_at=datetime.now(UTC),
        )
        # Case C: Inst 1, in RB (bureau 1) -> SAME bureau as Case A!
        case_c = Case(
            case_id="CC-2026-90003",
            institution_id=inst1.id,
            originating_bureau_id=rb.id,
            current_bureau_id=rb.id,
            receipt_at=datetime(2026, 10, 10, 10, 0, tzinfo=UTC),
            receipt_date=date(2026, 10, 10),
            source_channel="Portal",
            category="Approval",
            priority="Medium",
            subject="Alpha approval request",
            description="Approval description",
            status=CaseStatus.UNDER_PROCESS,
            last_action="Under process",
            last_action_at=datetime.now(UTC),
        )
        # Case D: Inst 2 (East region)
        case_d = Case(
            case_id="CC-2026-90004",
            institution_id=inst2.id,
            originating_bureau_id=rb.id,
            current_bureau_id=rb.id,
            receipt_at=datetime(2026, 10, 12, 10, 0, tzinfo=UTC),
            receipt_date=date(2026, 10, 12),
            source_channel="Portal",
            category="Faculty",
            priority="Low",
            subject="East faculty complaint",
            description="East complaint description",
            status=CaseStatus.RECEIVED,
            last_action="Received",
            last_action_at=datetime.now(UTC),
        )
        db.add_all([case_a, case_b, case_c, case_d])
        db.flush()

        # Overlap 1: Case A (RB) vs Case B (APB) -> Cross-bureau!
        ov_cross = OverlapCandidate(
            case_low_id=case_a.id,
            case_high_id=case_b.id,
            similarity_score=92,
            identity_match=True,
            reasons=["Same institution", "High text similarity"],
        )
        # Overlap 2: Case A (RB) vs Case C (RB) -> Same bureau!
        ov_same = OverlapCandidate(
            case_low_id=case_a.id,
            case_high_id=case_c.id,
            similarity_score=85,
            identity_match=False,
            reasons=["Same institution", "Category match"],
        )
        db.add_all([ov_cross, ov_same])
        db.flush()

        # Add an alert for Case A
        alert = Alert(
            dedupe_key=f"test_alert:{case_a.id}",
            alert_type="action_required",
            severity=AlertSeverity.WARNING,
            title="Clarification required",
            message="Please clarify application details",
            case_id=case_a.id,
            bureau_id=rb.id,
            region="North",
        )
        db.add(alert)
        db.commit()

        return {
            "admin_email": admin.email,
            "rep_email": rep1.email,
            "case_a_id": case_a.id,
            "case_a_ref": case_a.case_id,
            "case_b_id": case_b.id,
            "case_b_ref": case_b.case_id,
            "case_c_id": case_c.id,
            "case_d_id": case_d.id,
            "ov_cross_id": ov_cross.id,
            "ov_same_id": ov_same.id,
            "inst2_id": inst2.id,
            "inst2_perm_id": inst2.permanent_id,
        }


def get_token(client: TestClient, email: str) -> str:
    res = client.post("/api/auth/token", json={"email": email, "password": "Pass123!"})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_coordination_different_bureau_enforcement_and_overlap_metadata(client, setup_data):
    """Validates cross-bureau coordination succeeds while same-bureau returns 422."""
    token = get_token(client, setup_data["admin_email"])
    headers = {"Authorization": f"Bearer {token}"}

    # Verify context returns is_cross_bureau metadata
    ctx_res = client.get(f"/api/cases/{setup_data['case_a_ref']}/context", headers=headers)
    assert ctx_res.status_code == 200
    overlaps = ctx_res.json()["overlaps"]
    ov_cross = next(o for o in overlaps if o["id"] == setup_data["ov_cross_id"])
    ov_same = next(o for o in overlaps if o["id"] == setup_data["ov_same_id"])

    assert ov_cross["is_cross_bureau"] is True
    assert ov_same["is_cross_bureau"] is False

    # Attempt same-bureau coordination -> must fail with 422
    fail_res = client.post(
        f"/api/coordination/from-overlap/{setup_data['ov_same_id']}",
        json={"requesting_case_id": setup_data["case_a_id"], "reason": "Test same bureau"},
        headers=headers,
    )
    assert fail_res.status_code == 422
    # The app wraps HTTPExceptions as {"error": {"code": ..., "message": ...}}
    err_msg = fail_res.json()["error"]["message"]
    assert "different current bureaus" in err_msg

    # Attempt cross-bureau coordination -> must succeed
    succ_res = client.post(
        f"/api/coordination/from-overlap/{setup_data['ov_cross_id']}",
        json={"requesting_case_id": setup_data["case_a_id"], "reason": "Valid cross-bureau coordination"},
        headers=headers,
    )
    assert succ_res.status_code == 201
    coord = succ_res.json()
    assert coord["overlap_id"] == setup_data["ov_cross_id"]
    assert coord["status"] == "Pending Response"


def test_overview_filters_regions_categories_and_statuses(client, setup_data):
    """Validates region, category, and status filtering on summary analytics."""
    token = get_token(client, setup_data["admin_email"])
    headers = {"Authorization": f"Bearer {token}"}

    # Filter options should include North, East, Grievance, Approval, Faculty
    opts_res = client.get("/api/analytics/filter-options", headers=headers)
    assert opts_res.status_code == 200
    opts = opts_res.json()
    assert "North" in opts["regions"]
    assert "East" in opts["regions"]
    assert "Grievance" in opts["categories"]

    # Filter by Region=North
    r_north = client.get("/api/analytics/summary?region=North", headers=headers).json()
    assert r_north["total_received"] == 3  # cases A, B, C

    # Filter by Region=north (case-insensitive)
    r_north_ci = client.get("/api/analytics/summary?region=north", headers=headers).json()
    assert r_north_ci["total_received"] == 3

    # Filter by Region=East
    r_east = client.get("/api/analytics/summary?region=East", headers=headers).json()
    assert r_east["total_received"] == 1  # case D

    # Filter by Category=Grievance
    r_griev = client.get("/api/analytics/summary?category=Grievance", headers=headers).json()
    assert r_griev["total_received"] == 2  # cases A, B

    # Combined filter: Region=North AND Category=Approval
    r_comb = client.get("/api/analytics/summary?region=North&category=Approval", headers=headers).json()
    assert r_comb["total_received"] == 1  # case C

    # Filter with no match: Region=West
    r_west = client.get("/api/analytics/summary?region=West", headers=headers).json()
    assert r_west["total_received"] == 0


def test_portal_application_lookup_by_both_numeric_id_and_public_reference(client, setup_data):
    """Validates institution user can open application by public ref or numeric ID, and alerts return case_reference."""
    rep_token = get_token(client, setup_data["rep_email"])
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    # Lookup by public reference (e.g. "CC-2026-90001")
    res_pub = client.get(f"/api/portal/applications/{setup_data['case_a_ref']}", headers=rep_headers)
    assert res_pub.status_code == 200
    assert res_pub.json()["case"]["case_id"] == setup_data["case_a_ref"]

    # Lookup by numeric ID (e.g. 1 or string "1")
    res_num = client.get(f"/api/portal/applications/{setup_data['case_a_id']}", headers=rep_headers)
    assert res_num.status_code == 200
    assert res_num.json()["case"]["case_id"] == setup_data["case_a_ref"]

    # Alerts endpoint returns case_reference
    alerts_res = client.get("/api/portal/alerts", headers=rep_headers)
    assert alerts_res.status_code == 200
    alert_item = alerts_res.json()[0]
    assert alert_item["case_reference"] == setup_data["case_a_ref"]

    # Non-existent application returns 404
    not_found = client.get("/api/portal/applications/CC-2026-99999", headers=rep_headers)
    assert not_found.status_code == 404

    # Case from another institution (Case D is inst2) returns 404 for rep1
    foreign = client.get(f"/api/portal/applications/{setup_data['case_d_id']}", headers=rep_headers)
    assert foreign.status_code == 404


def test_institution_search_by_permanent_id_and_accounts(client, setup_data):
    """Validates institution search by permanent ID and profile accounts section."""
    token = get_token(client, setup_data["admin_email"])
    headers = {"Authorization": f"Bearer {token}"}

    # Search by permanent ID "DEMO-AICTE-0003"
    search_res = client.get(f"/api/institutions?search={setup_data['inst2_perm_id']}", headers=headers)
    assert search_res.status_code == 200
    items = search_res.json()
    assert len(items) == 1
    assert items[0]["permanent_id"] == setup_data["inst2_perm_id"]

    # Institution 1 profile has accounts (rep1)
    p1 = client.get("/api/institutions/1/profile", headers=headers).json()
    assert len(p1["accounts"]) >= 1
    assert any(acc["email"] == setup_data["rep_email"] for acc in p1["accounts"])

    # Institution 2 profile has 0 accounts
    p2 = client.get(f"/api/institutions/{setup_data['inst2_id']}/profile", headers=headers).json()
    assert p2["accounts"] == []
