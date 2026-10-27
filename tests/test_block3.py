# ruff: noqa: F401, F811
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import Institution
from app.services import normalize_name
from tests.test_api import case_payload, client, setup_data, token


def test_permanent_id_normalization_profile_and_audit(client, setup_data):
    admin = token(client, "admin@test.example.com")
    created = client.post("/api/institutions", headers=admin, json={
        "permanent_id": "  demo  id - 77  ", "name": "  Normalized   Institution ",
        "institution_type": "  College ", "region": " North ",
    })
    assert created.status_code == 201
    institution = created.json()
    assert institution["permanent_id"] == "DEMO ID - 77"
    assert institution["name"] == "Normalized Institution"
    duplicate = client.post("/api/institutions", headers=admin, json={
        "permanent_id": "demo id - 77", "name": "Different Synthetic College", "institution_type": "College", "region": "North",
    })
    assert duplicate.status_code == 409
    # Deliberately different punctuation remains distinct: no unsupported
    # AICTE-format inference or over-aggressive identifier merging is applied.
    distinct = client.post("/api/institutions", headers=admin, json={
        "permanent_id": "DEMO ID-77", "name": "Distinct Format Synthetic College", "institution_type": "College", "region": "North",
    })
    assert distinct.status_code == 201
    found = client.get("/api/institutions", headers=admin, params={"permanent_id": " demo id - 77 "})
    assert found.status_code == 200 and found.json()[0]["id"] == institution["id"]

    first = client.post("/api/cases", headers=admin, json=case_payload(setup_data)).json()
    second_payload = case_payload(setup_data)
    second_payload["subject"] = "Another synthetic institution complaint"
    second = client.post("/api/cases", headers=admin, json=second_payload).json()
    profile = client.get(f"/api/institutions/{setup_data['institution']}/profile", headers=admin)
    assert profile.status_code == 200
    assert profile.json()["total_cases"] == 2
    assert {item["case_id"] for item in profile.json()["cases"]} == {first["case_id"], second["case_id"]}

    changed = client.patch(f"/api/institutions/{institution['id']}", headers=admin, json={"city": "Synthetic City"})
    assert changed.status_code == 200
    audit = client.get("/api/audit-events", headers=admin).json()
    update_event = next(item for item in audit if item["action"] == "institution_updated")
    assert update_event["details"]["before"]["city"] is None
    assert update_event["details"]["after"]["city"] == "Synthetic City"


def test_institution_profile_respects_regional_access(client, setup_data):
    north = token(client, "north@test.example.com")
    assert client.get(f"/api/institutions/{setup_data['institution']}/profile", headers=north).status_code == 200
    assert client.get(f"/api/institutions/{setup_data['south_institution']}/profile", headers=north).status_code == 403
    assert client.patch(f"/api/institutions/{setup_data['institution']}", headers=token(client, "rb@test.example.com"), json={"region": "South"}).status_code == 403


def test_profile_empty_unknown_scoped_and_related_overlap_records(client, setup_data):
    admin = token(client, "admin@test.example.com")
    empty = client.post("/api/institutions", headers=admin, json={
        "permanent_id": " \t ", "name": "Empty Synthetic Institution",
        "institution_type": "College", "region": "North",
    })
    assert empty.status_code == 201
    assert empty.json()["permanent_id"] is None
    assert empty.json()["permanent_id_verified"] is False
    empty_profile = client.get(f"/api/institutions/{empty.json()['id']}/profile", headers=admin)
    assert empty_profile.status_code == 200
    assert empty_profile.json()["total_cases"] == 0
    assert empty_profile.json()["cases"] == []
    assert empty_profile.json()["related_overlaps"] == []
    assert client.get("/api/institutions/999999/profile", headers=admin).status_code == 404

    first = case_payload(setup_data)
    first.update({"subject": "Synthetic equipment condition issue", "description": "Fictional complaint about a missing laboratory condition.", "external_reference": "BLOCK3-RELATED"})
    second = case_payload(setup_data)
    second.update({
        "subject": "Equipment condition issue at institution",
        "description": "Fictional complaint about a missing laboratory condition.",
        "external_reference": "BLOCK3-RELATED", "current_bureau_id": setup_data["pgrc"],
    })
    first_created = client.post("/api/cases", headers=admin, json=first)
    second_created = client.post("/api/cases", headers=admin, json=second)
    assert first_created.status_code == 201
    assert second_created.status_code == 201
    assert client.post("/api/overlaps/refresh", headers=admin).status_code == 200
    profile = client.get(f"/api/institutions/{setup_data['institution']}/profile", headers=admin).json()
    assert profile["total_cases"] == 2
    assert sum(profile["cases_by_status"].values()) == profile["total_cases"]
    assert len({item["case_id"] for item in profile["cases"]}) == 2
    assert len(profile["related_overlaps"]) == 1
    overlap = profile["related_overlaps"][0]
    assert overlap["case_id"] != overlap["related_case_id"]
    coordination = client.post(
        f"/api/coordination/from-overlap/{overlap['id']}",
        headers=admin,
        json={"requesting_case_id": first_created.json()["id"], "reason": "Please review this synthetic related matter."},
    )
    assert coordination.status_code == 201
    profile = client.get(f"/api/institutions/{setup_data['institution']}/profile", headers=admin).json()
    assert [item["id"] for item in profile["related_coordination"]] == [coordination.json()["id"]]

    # APB is neither originating nor current bureau for these cases.  It may see
    # non-sensitive institution metadata, but the profile must expose no cases.
    restricted = client.get(f"/api/institutions/{setup_data['institution']}/profile", headers=token(client, "apb@test.example.com"))
    assert restricted.status_code == 200
    assert restricted.json()["total_cases"] == 0
    assert restricted.json()["cases"] == []
    assert restricted.json()["related_overlaps"] == []
    assert restricted.json()["related_coordination"] == []


def test_permanent_id_update_conflict_rolls_back_and_audit_is_immutable(client, setup_data):
    admin = token(client, "admin@test.example.com")
    first = client.post("/api/institutions", headers=admin, json={
        "permanent_id": "BLOCK3-FIRST", "name": "First Synthetic Institution", "institution_type": "College", "region": "North",
    }).json()
    second = client.post("/api/institutions", headers=admin, json={
        "permanent_id": "BLOCK3-SECOND", "name": "Second Synthetic Institution", "institution_type": "College", "region": "North",
    }).json()
    failed = client.patch(f"/api/institutions/{first['id']}", headers=admin, json={
        "permanent_id": "  block3-second ", "name": "This update must not persist",
    })
    assert failed.status_code == 409
    persisted = client.get(f"/api/institutions/{first['id']}", headers=admin).json()
    assert persisted["permanent_id"] == "BLOCK3-FIRST"
    assert persisted["name"] == "First Synthetic Institution"
    assert second["permanent_id"] == "BLOCK3-SECOND"

    audit = client.get("/api/audit-events", headers=admin).json()
    creation = next(item for item in audit if item["action"] == "institution_created" and item["entity_id"] == str(first["id"]))
    assert creation["actor_id"] is not None
    assert creation["created_at"]
    assert creation["details"]["permanent_id"] == "BLOCK3-FIRST"
    assert "password" not in str(creation["details"]).casefold()
    assert client.get("/api/audit-events", headers=token(client, "rb@test.example.com")).status_code == 403
    # There is deliberately no mutation route for audit events.
    assert client.delete(f"/api/audit-events/{creation['id']}", headers=admin).status_code == 404


def test_database_unique_constraint_rejects_simultaneous_permanent_id_inserts():
    """The database, not only API pre-checks, is the final duplicate guard."""
    gate = Barrier(2)

    def insert() -> str:
        with SessionLocal() as db:
            gate.wait()
            db.add(Institution(
                permanent_id="CONCURRENT-BLOCK3-ID", permanent_id_verified=False,
                name="Concurrent Synthetic Institution", normalized_name=normalize_name("Concurrent Synthetic Institution"),
                institution_type="College", region="North", status="Active",
            ))
            try:
                db.commit()
                return "created"
            except IntegrityError:
                db.rollback()
                return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: insert(), range(2)))
    assert sorted(outcomes) == ["created", "duplicate"]
