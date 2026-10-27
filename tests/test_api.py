from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.enums import Role
from app.main import app
from app.models import Bureau, Case, Institution, User
from app.security import hash_password
from app.seed import seed
from app.services import normalize_name


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def setup_data():
    with SessionLocal() as db:
        rb, pgrc, apb = Bureau(code="RB", name="Regulation Bureau"), Bureau(code="PGRC", name="Public Grievance"), Bureau(code="APB", name="Approval Bureau")
        db.add_all([rb, pgrc, apb])
        db.flush()
        admin = User(email="admin@test.example.com", full_name="Admin", password_hash=hash_password("Pass123!"), role=Role.ADMIN, bureau_id=rb.id, region_scope="ALL")
        rb_user = User(email="rb@test.example.com", full_name="RB", password_hash=hash_password("Pass123!"), role=Role.RB_OFFICER, bureau_id=rb.id)
        pgrc_user = User(email="pgrc@test.example.com", full_name="PGRC", password_hash=hash_password("Pass123!"), role=Role.PGRC_OFFICER, bureau_id=pgrc.id)
        apb_user = User(email="apb@test.example.com", full_name="APB", password_hash=hash_password("Pass123!"), role=Role.OTHER_BUREAU_OFFICER, bureau_id=apb.id)
        north_user = User(email="north@test.example.com", full_name="North", password_hash=hash_password("Pass123!"), role=Role.REGIONAL_OFFICER, bureau_id=apb.id, region_scope="North")
        db.add_all([admin, rb_user, pgrc_user, apb_user, north_user])
        institution = Institution(permanent_id="TEST-001", permanent_id_verified=True, name="Test Institute", normalized_name=normalize_name("Test Institute"), institution_type="College", region="North", status="Active")
        south_institution = Institution(permanent_id="TEST-002", permanent_id_verified=False, name="South Test Institute", normalized_name=normalize_name("South Test Institute"), institution_type="College", region="South", status="Active")
        db.add_all([institution, south_institution])
        db.commit()
        return {
            "rb": rb.id,
            "pgrc": pgrc.id,
            "apb": apb.id,
            "institution": institution.id,
            "south_institution": south_institution.id,
            "rb_user": rb_user.id,
            "pgrc_user": pgrc_user.id,
        }


def token(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/token", json={"email": email, "password": "Pass123!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def case_payload(data: dict[str, int]) -> dict:
    return {"institution_id": data["institution"], "receipt_at": datetime.now(UTC).isoformat(), "source_channel": "Portal", "category": "Approval", "subject": "A sufficiently detailed synthetic subject", "description": "A sufficiently detailed fictional complaint description.", "originating_bureau_id": data["rb"], "expected_disposal_date": datetime.now(UTC).isoformat()}


def test_health_auth_and_institution_uniqueness(client, setup_data):
    assert client.get("/health").json()["status"] == "ok"
    headers = token(client, "admin@test.example.com")
    duplicate = {"permanent_id": "TEST-001", "permanent_id_verified": True, "name": "Another Test Institute", "institution_type": "College", "region": "North"}
    response = client.post("/api/institutions", json=duplicate, headers=headers)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "http_error"


def test_case_creation_filters_history_and_transition_validation(client, setup_data):
    admin_headers = token(client, "admin@test.example.com")
    first = client.post("/api/cases", json=case_payload(setup_data), headers=admin_headers)
    second = client.post("/api/cases", json=case_payload(setup_data), headers=admin_headers)
    assert first.status_code == 201 and second.status_code == 201
    case_id = first.json()["case_id"]
    assert case_id != second.json()["case_id"]
    filtered = client.get("/api/cases", params={"permanent_id": "TEST-001", "status": "Received"}, headers=admin_headers)
    assert filtered.status_code == 200 and filtered.json()["total"] == 2
    invalid = client.patch(f"/api/cases/{case_id}", json={"status": "Disposed"}, headers=admin_headers)
    assert invalid.status_code == 422
    assert client.get(f"/api/cases/{case_id}/history", headers=admin_headers).json()[0]["action_type"] == "created"


def test_bureau_restrictions_and_history_persist(client, setup_data):
    admin_headers = token(client, "admin@test.example.com")
    created = client.post("/api/cases", json=case_payload(setup_data), headers=admin_headers).json()
    case_id = created["case_id"]
    assert client.get(f"/api/cases/{case_id}", headers=token(client, "apb@test.example.com")).status_code == 403
    transfer = client.post(f"/api/cases/{case_id}/actions", json={"action_type": "transferred", "target_bureau_id": setup_data["pgrc"], "remarks": "Transfer for grievance review"}, headers=admin_headers)
    assert transfer.status_code == 200 and transfer.json()["status"] == "Transferred"
    assert client.get(f"/api/cases/{case_id}", headers=token(client, "pgrc@test.example.com")).status_code == 200
    history = client.get(f"/api/cases/{case_id}/history", headers=admin_headers).json()
    assert len(history) == 2 and history[-1]["action_type"] == "transferred"


def test_complete_case_workflow_validation_and_restart_persistence(client, setup_data):
    admin_headers = token(client, "admin@test.example.com")
    institution = client.post("/api/institutions", json={
        "permanent_id": "TEST-NEW-001", "permanent_id_verified": True,
        "name": "New Synthetic Institution", "institution_type": "College", "region": "North",
    }, headers=admin_headers)
    assert institution.status_code == 201
    institution_id = institution.json()["id"]
    assert client.get(f"/api/institutions/{institution_id}", headers=admin_headers).status_code == 200
    assert client.post("/api/institutions", json={
        "permanent_id": "TEST-NEW-001", "name": "Duplicate Synthetic Institution",
        "institution_type": "College", "region": "North",
    }, headers=admin_headers).status_code == 409
    assert client.post("/api/cases", json={"institution_id": institution_id}, headers=admin_headers).status_code == 422

    payload = case_payload({**setup_data, "institution": institution_id})
    created = client.post("/api/cases", json=payload, headers=admin_headers)
    assert created.status_code == 201
    case_id = created.json()["case_id"]
    updated = client.patch(f"/api/cases/{case_id}", json={
        "status": "Under Review", "assigned_officer_id": setup_data["rb_user"], "remarks": "Assigned for initial review",
    }, headers=admin_headers)
    assert updated.status_code == 200
    assert updated.json()["status"] == "Under Review"
    assert updated.json()["assigned_officer_id"] == setup_data["rb_user"]
    mismatched_assignment = client.patch(f"/api/cases/{case_id}", json={"assigned_officer_id": setup_data["pgrc_user"]}, headers=admin_headers)
    assert mismatched_assignment.status_code == 422
    assert mismatched_assignment.json()["error"]["message"] == "Assigned officer must belong to the current bureau"
    note = client.post(f"/api/cases/{case_id}/actions", json={"action_type": "note", "remarks": "Synthetic supporting note"}, headers=admin_headers)
    assert note.status_code == 200
    transfer = client.post(f"/api/cases/{case_id}/actions", json={
        "action_type": "transferred", "target_bureau_id": setup_data["pgrc"], "remarks": "Transfer for review",
    }, headers=admin_headers)
    assert transfer.status_code == 200 and transfer.json()["current_bureau_id"] == setup_data["pgrc"]
    reassigned = client.post(f"/api/cases/{case_id}/actions", json={
        "action_type": "assigned", "assigned_officer_id": setup_data["pgrc_user"], "remarks": "Assigned after transfer",
    }, headers=admin_headers)
    assert reassigned.status_code == 200 and reassigned.json()["assigned_officer_id"] == setup_data["pgrc_user"]
    assert client.get(f"/api/cases/{case_id}", headers=admin_headers).status_code == 200
    institution_cases = client.get(f"/api/institutions/{institution_id}/cases", headers=admin_headers)
    assert institution_cases.status_code == 200
    assert any(item["case_id"] == case_id for item in institution_cases.json())

    # A fresh application client uses the same database and confirms committed persistence.
    with TestClient(app) as restarted_client:
        assert restarted_client.get(f"/api/cases/{case_id}", headers=admin_headers).json()["case_id"] == case_id


def test_bureau_officer_cannot_spoof_originating_bureau(client, setup_data):
    rb_headers = token(client, "rb@test.example.com")
    payload = case_payload(setup_data)
    payload["originating_bureau_id"] = setup_data["pgrc"]
    payload["current_bureau_id"] = setup_data["rb"]
    response = client.post("/api/cases", json=payload, headers=rb_headers)
    assert response.status_code == 403


def test_escalation_and_regional_scope(client, setup_data):
    admin_headers = token(client, "admin@test.example.com")
    created = client.post("/api/cases", json=case_payload(setup_data), headers=admin_headers).json()
    case_id = created["case_id"]
    escalated = client.post(f"/api/cases/{case_id}/actions", json={
        "action_type": "escalated", "remarks": "Escalated in synthetic test",
    }, headers=admin_headers)
    assert escalated.status_code == 200 and escalated.json()["status"] == "Escalated"
    north_headers = token(client, "north@test.example.com")
    visible = client.get("/api/institutions", headers=north_headers).json()
    assert {item["region"] for item in visible} == {"North"}
    assert client.get(f"/api/institutions/{setup_data['south_institution']}", headers=north_headers).status_code == 403


def test_seed_is_repeatable_and_contains_required_volume():
    seed()
    seed()
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Institution.id))) == 20
        assert db.scalar(select(func.count(Case.id))) == 40
        assert db.scalar(select(func.count(Bureau.id))) >= 5
