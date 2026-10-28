"""Institution Representative portal regression tests."""
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.enums import Role
from app.main import app
from app.models import Bureau, Institution, User
from app.security import hash_password
from app.services import normalize_name


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def portal_data():
    """Seed a minimal dataset with institutions, reps, and admin."""
    with SessionLocal() as db:
        rb = Bureau(code="RB", name="Regulation Bureau")
        db.add(rb)
        db.flush()
        institution = Institution(
            permanent_id="PORTAL-001",
            permanent_id_verified=False,
            name="Portal Test Institute",
            normalized_name=normalize_name("Portal Test Institute"),
            institution_type="College",
            region="North",
            status="Active",
        )
        other_institution = Institution(
            permanent_id="PORTAL-002",
            permanent_id_verified=False,
            name="Other Institute",
            normalized_name=normalize_name("Other Institute"),
            institution_type="University",
            region="South",
            status="Active",
        )
        db.add_all([institution, other_institution])
        db.flush()
        rep = User(
            email="rep@portal.example.com",
            full_name="Institution Rep",
            password_hash=hash_password("Pass123!"),
            role=Role.INSTITUTION_REPRESENTATIVE,
            bureau_id=rb.id,
            institution_id=institution.id,
            is_active=True,
        )
        admin = User(
            email="admin@portal.example.com",
            full_name="Admin",
            password_hash=hash_password("Pass123!"),
            role=Role.ADMIN,
            bureau_id=rb.id,
            region_scope="ALL",
            is_active=True,
        )
        # A rep for the other institution — must not see PORTAL-001 cases
        other_rep = User(
            email="otherrep@portal.example.com",
            full_name="Other Rep",
            password_hash=hash_password("Pass123!"),
            role=Role.INSTITUTION_REPRESENTATIVE,
            bureau_id=rb.id,
            institution_id=other_institution.id,
            is_active=True,
        )
        db.add_all([rep, admin, other_rep])
        db.commit()
        return {
            "rb": rb.id,
            "institution": institution.id,
            "other_institution": other_institution.id,
        }


def _token(client: TestClient, email: str) -> dict[str, str]:
    resp = client.post("/api/auth/token", json={"email": email, "password": "Pass123!"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# 1. Authentication and role routing
# ---------------------------------------------------------------------------

def test_institution_rep_login_succeeds_and_exposes_institution_id(client, portal_data):
    resp = client.post("/api/auth/token", json={"email": "rep@portal.example.com", "password": "Pass123!"})
    assert resp.status_code == 200
    auth = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    me = client.get("/api/auth/me", headers=auth).json()
    assert me["role"] == Role.INSTITUTION_REPRESENTATIVE
    assert me["institution_id"] == portal_data["institution"]


def test_unauthenticated_portal_request_is_rejected(client, portal_data):
    assert client.get("/api/portal/overview").status_code == 401


def test_admin_cannot_access_portal_endpoints(client, portal_data):
    auth = _token(client, "admin@portal.example.com")
    # Admin is not an Institution Representative — portal guard must reject
    assert client.get("/api/portal/overview", headers=auth).status_code == 403
    assert client.get("/api/portal/applications", headers=auth).status_code == 403


# ---------------------------------------------------------------------------
# 2. Portal overview
# ---------------------------------------------------------------------------

def test_portal_overview_returns_metrics_for_own_institution(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    resp = client.get("/api/portal/overview", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_applications" in data
    assert "institution_id" in data
    assert data["institution_id"] == portal_data["institution"]
    assert data["total_applications"] == 0


# ---------------------------------------------------------------------------
# 3. Application submission and server-side resolution
# ---------------------------------------------------------------------------

def test_rep_can_submit_application_without_client_institution_or_bureau_ids(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    # No client-side institution_id or originating_bureau_id is sent;
    # backend resolves both from the authenticated representative session.
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Synthetic portal submission without client-provided IDs",
        "description": "A detailed description of this synthetic test application.",
    }
    resp = client.post("/api/cases", json=payload, headers=auth)
    assert resp.status_code == 201
    case = resp.json()
    assert case["institution_id"] == portal_data["institution"]
    assert case["originating_bureau_id"] == portal_data["rb"]


def test_rep_cannot_override_institution_id(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    # Attempting to forge another institution's ID is overridden server-side
    payload = {
        "institution_id": portal_data["other_institution"],
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Attempting forge institution ID",
        "description": "Server must bind to the authorized institution_id.",
    }
    resp = client.post("/api/cases", json=payload, headers=auth)
    assert resp.status_code == 201
    case = resp.json()
    assert case["institution_id"] == portal_data["institution"]


def test_admin_submitting_without_institution_id_fails_validation(client, portal_data):
    auth = _token(client, "admin@portal.example.com")
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Admin missing institution ID",
        "description": "Admin must supply institution_id.",
        "originating_bureau_id": portal_data["rb"],
    }
    resp = client.post("/api/cases", json=payload, headers=auth)
    assert resp.status_code == 422


def test_rep_without_bureau_resolves_configured_intake_bureau(client, portal_data):
    # Rep without bureau_id falls back to configured intake bureau
    with SessionLocal() as db:
        rep_no_bureau = User(
            email="nobureau@portal.example.com",
            full_name="No Bureau Rep",
            password_hash=hash_password("Pass123!"),
            role=Role.INSTITUTION_REPRESENTATIVE,
            bureau_id=None,
            institution_id=portal_data["institution"],
            is_active=True,
        )
        db.add(rep_no_bureau)
        db.commit()

    auth = _token(client, "nobureau@portal.example.com")
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Intake bureau fallback test",
        "description": "Testing automatic fallback to configured bureau.",
    }
    resp = client.post("/api/cases", json=payload, headers=auth)
    assert resp.status_code == 201
    case = resp.json()
    assert case["institution_id"] == portal_data["institution"]
    assert case["originating_bureau_id"] == portal_data["rb"]


def test_rep_sees_only_own_institution_applications(client, portal_data):
    rep_auth = _token(client, "rep@portal.example.com")
    other_auth = _token(client, "otherrep@portal.example.com")
    admin_auth = _token(client, "admin@portal.example.com")

    # Rep submits one application
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal", "category": "Application",
        "priority": "Medium", "subject": "Isolation test application",
        "description": "Verifying that only the submitting institution rep sees this.",
    }
    resp = client.post("/api/cases", json=payload, headers=rep_auth)
    assert resp.status_code == 201
    case_id = resp.json()["case_id"]

    # Rep sees it
    my_apps = client.get("/api/portal/applications", headers=rep_auth).json()
    assert any(a["case_id"] == case_id for a in my_apps)

    # Other rep does NOT see it
    other_apps = client.get("/api/portal/applications", headers=other_auth).json()
    assert not any(a["case_id"] == case_id for a in other_apps)

    # Admin can see it via the standard API
    admin_resp = client.get(f"/api/cases?case_id={case_id}", headers=admin_auth).json()
    assert admin_resp["total"] >= 1


def test_rep_can_retrieve_own_application_detail(client, portal_data):
    rep_auth = _token(client, "rep@portal.example.com")
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal", "category": "Application",
        "priority": "Medium", "subject": "Detail retrieval test",
        "description": "Testing the application detail endpoint.",
    }
    case_id = client.post("/api/cases", json=payload, headers=rep_auth).json()["case_id"]
    detail = client.get(f"/api/portal/applications/{case_id}", headers=rep_auth).json()
    assert "case" in detail
    assert "history" in detail
    assert "alerts" in detail
    assert detail["case"]["case_id"] == case_id


def test_other_rep_cannot_retrieve_foreign_application_detail(client, portal_data):
    rep_auth = _token(client, "rep@portal.example.com")
    other_auth = _token(client, "otherrep@portal.example.com")
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal", "category": "Application",
        "priority": "Medium", "subject": "Foreign access test",
        "description": "The other rep must not see this application.",
    }
    case_id = client.post("/api/cases", json=payload, headers=rep_auth).json()["case_id"]
    resp = client.get(f"/api/portal/applications/{case_id}", headers=other_auth)
    assert resp.status_code == 404


def test_rep_without_institution_assignment_is_rejected(client, portal_data):
    # Create a rep user with no institution_id
    with SessionLocal() as db:
        unlinked = User(
            email="unlinked@portal.example.com",
            full_name="Unlinked Rep",
            password_hash=hash_password("Pass123!"),
            role=Role.INSTITUTION_REPRESENTATIVE,
            bureau_id=portal_data["rb"],
            institution_id=None,
            is_active=True,
        )
        db.add(unlinked)
        db.commit()
    auth = _token(client, "unlinked@portal.example.com")
    assert client.get("/api/portal/overview", headers=auth).status_code == 403
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Unlinked rep submit test",
        "description": "Must be rejected.",
    }
    assert client.post("/api/cases", json=payload, headers=auth).status_code == 403


# ---------------------------------------------------------------------------
# 4. Portal institution endpoint
# ---------------------------------------------------------------------------

def test_portal_institution_returns_own_record(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    resp = client.get("/api/portal/institution", headers=auth)
    assert resp.status_code == 200
    inst = resp.json()
    assert inst["permanent_id"] == "PORTAL-001"
    assert inst["name"] == "Portal Test Institute"


# ---------------------------------------------------------------------------
# 5. Portal alerts endpoint
# ---------------------------------------------------------------------------

def test_portal_alerts_returns_list_for_own_institution(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    resp = client.get("/api/portal/alerts", headers=auth)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 6. Portal documents and clarification response
# ---------------------------------------------------------------------------

def test_portal_documents_returns_dockets_for_own_institution(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    # Submit one application so documents has content
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Document docket test",
        "description": "Checking portal documents listing.",
    }
    client.post("/api/cases", json=payload, headers=auth)
    resp = client.get("/api/portal/documents", headers=auth)
    assert resp.status_code == 200
    docs = resp.json()
    assert len(docs) >= 1
    assert "case_id" in docs[0]
    assert "document_type" in docs[0]


def test_portal_respond_records_clarification(client, portal_data):
    auth = _token(client, "rep@portal.example.com")
    payload = {
        "receipt_date": datetime.now(UTC).date().isoformat(),
        "source_channel": "Institution Portal",
        "category": "Application",
        "priority": "Medium",
        "subject": "Clarification test case",
        "description": "Testing clarification response.",
    }
    case_id = client.post("/api/cases", json=payload, headers=auth).json()["case_id"]

    resp = client.post(f"/api/portal/applications/{case_id}/respond", json={"remarks": "Uploaded revised building compliance certificate."}, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

    # Detail view reflects the clarification note in history
    detail = client.get(f"/api/portal/applications/{case_id}", headers=auth).json()
    assert any("building compliance" in str(e.get("remarks")) for e in detail["history"])
