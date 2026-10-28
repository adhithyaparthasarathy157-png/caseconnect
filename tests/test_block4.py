# ruff: noqa: F401, F811
from tests.test_api import client, setup_data, token
from tests.test_block2 import create_related_cases


def test_cross_bureau_coordination_is_persisted_authorized_and_audited(client, setup_data):
    admin = token(client, "admin@test.example.com")
    create_related_cases(client, admin, setup_data)
    assert client.post("/api/overlaps/refresh", headers=admin).status_code == 200
    candidate = client.get("/api/overlaps", headers=admin).json()[0]

    invalid_source = client.post(
        f"/api/coordination/from-overlap/{candidate['id']}",
        headers=admin,
        json={"requesting_case_id": 99999, "reason": "Synthetic coordination reason"},
    )
    assert invalid_source.status_code == 422
    created = client.post(
        f"/api/coordination/from-overlap/{candidate['id']}",
        headers=admin,
        json={"requesting_case_id": candidate["case_low_id"], "reason": "Please compare the fictional related matters."},
    )
    assert created.status_code == 201
    request = created.json()
    assert request["status"] == "Pending Response"
    assert request["requesting_case_id"] == candidate["case_low_id"]
    assert request["receiving_case_id"] == candidate["case_high_id"]
    assert request["requesting_bureau_id"] != request["receiving_bureau_id"]
    assert client.post(
        f"/api/coordination/from-overlap/{candidate['id']}",
        headers=admin,
        json={"requesting_case_id": candidate["case_low_id"], "reason": "Duplicate request"},
    ).status_code == 409

    source_officer = token(client, "rb@test.example.com")
    assert client.post(
        f"/api/coordination/{request['id']}/respond",
        headers=source_officer,
        json={"status": "Responded", "response": "This must be rejected for the requesting bureau."},
    ).status_code == 403
    receiving_officer = token(client, "pgrc@test.example.com")
    response = client.post(
        f"/api/coordination/{request['id']}/respond",
        headers=receiving_officer,
        json={"status": "Responded", "response": "Receiving bureau reviewed the synthetic overlap."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "Responded"
    assert response.json()["responded_by_id"] == setup_data["pgrc_user"]

    assert client.get("/api/coordination", headers=token(client, "apb@test.example.com")).json() == []
    pgrc_alerts = client.get("/api/alerts", headers=receiving_officer).json()
    assert any(item["alert_type"] == "coordination_requested" for item in pgrc_alerts)
    audit = client.get("/api/audit-events", headers=admin).json()
    assert any(item["action"] == "coordination_requested" and item["entity_id"] == request["id"] for item in audit)
    assert any(item["action"] == "coordination_responded" and item["entity_id"] == request["id"] for item in audit)


def test_case_context_and_workflow_reference_data_are_scoped(client, setup_data):
    admin = token(client, "admin@test.example.com")
    created = client.post("/api/cases", headers=admin, json={
        "institution_id": setup_data["institution"], "receipt_date": "2026-10-27",
        "source_channel": "Portal", "category": "Approval", "subject": "Synthetic context workflow case",
        "description": "A sufficiently detailed synthetic context workflow description.",
        "originating_bureau_id": setup_data["rb"], "expected_disposal_date": "2026-10-30T10:00:00Z",
    }).json()
    context = client.get(f"/api/cases/{created['case_id']}/context", headers=admin)
    assert context.status_code == 200
    assert context.json()["case"]["case_id"] == created["case_id"]
    assert context.json()["history"][0]["action_type"] == "created"
    bureaus = client.get("/api/reference/bureaus", headers=admin)
    assert bureaus.status_code == 200 and {item["id"] for item in bureaus.json()} >= {setup_data["rb"], setup_data["pgrc"]}
    officers = client.get("/api/reference/officers", params={"bureau_id": setup_data["rb"]}, headers=token(client, "rb@test.example.com"))
    assert officers.status_code == 200
    assert client.get("/api/reference/officers", params={"bureau_id": setup_data["pgrc"]}, headers=token(client, "rb@test.example.com")).status_code == 403
    assert client.get(f"/api/cases/{created['case_id']}/context", headers=token(client, "apb@test.example.com")).status_code == 403


def test_same_bureau_transfer_is_rejected_without_case_or_history_change(client, setup_data):
    admin = token(client, "admin@test.example.com")
    created = client.post("/api/cases", headers=admin, json={
        "institution_id": setup_data["institution"], "receipt_date": "2026-10-27",
        "source_channel": "Portal", "category": "Approval", "subject": "Synthetic transfer integrity case",
        "description": "A sufficiently detailed synthetic transfer integrity description.",
        "originating_bureau_id": setup_data["rb"],
    }).json()
    rejected = client.post(f"/api/cases/{created['case_id']}/actions", headers=admin, json={
        "action_type": "transferred", "target_bureau_id": setup_data["rb"], "remarks": "Invalid same bureau transfer",
    })
    assert rejected.status_code == 422
    persisted = client.get(f"/api/cases/{created['case_id']}", headers=admin).json()
    history = client.get(f"/api/cases/{created['case_id']}/history", headers=admin).json()
    assert persisted["current_bureau_id"] == setup_data["rb"]
    assert persisted["status"] == "Received"
    assert [event["action_type"] for event in history] == ["created"]


def test_alert_actions_are_authorized_persistent_and_idempotent(client, setup_data):
    admin = token(client, "admin@test.example.com")
    created = client.post("/api/cases", headers=admin, json={
        "institution_id": setup_data["institution"], "receipt_date": "2026-10-27",
        "source_channel": "Portal", "category": "Approval", "subject": "Synthetic alert lifecycle case",
        "description": "A sufficiently detailed synthetic alert lifecycle description.",
        "originating_bureau_id": setup_data["rb"],
    }).json()
    assert client.post(f"/api/cases/{created['case_id']}/actions", headers=admin, json={
        "action_type": "escalated", "remarks": "Create a synthetic escalation alert",
    }).status_code == 200
    alert = next(item for item in client.get("/api/alerts", headers=admin).json() if item["case_id"] == created["id"])
    assert client.post(f"/api/alerts/{alert['id']}/acknowledge", headers=token(client, "apb@test.example.com")).status_code == 403
    acknowledged = client.post(f"/api/alerts/{alert['id']}/acknowledge", headers=admin)
    assert acknowledged.status_code == 200 and acknowledged.json()["acknowledged_at"]
    audit_before = [item for item in client.get("/api/audit-events", headers=admin).json() if item["entity_id"] == alert["id"] and item["action"] == "alert_acknowledge"]
    assert client.post(f"/api/alerts/{alert['id']}/acknowledge", headers=admin).status_code == 200
    audit_after = [item for item in client.get("/api/audit-events", headers=admin).json() if item["entity_id"] == alert["id"] and item["action"] == "alert_acknowledge"]
    assert len(audit_after) == len(audit_before) == 1
    resolved = client.post(f"/api/alerts/{alert['id']}/resolve", headers=admin)
    assert resolved.status_code == 200 and resolved.json()["resolved_at"]
    assert client.post(f"/api/alerts/{alert['id']}/resolve", headers=admin).status_code == 422
    assert client.post(f"/api/alerts/{alert['id']}/acknowledge", headers=admin).status_code == 422
