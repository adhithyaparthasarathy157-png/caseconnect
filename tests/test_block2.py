# ruff: noqa: F401, F811

from fastapi.testclient import TestClient

from tests.test_api import case_payload, client, setup_data, token


def create_related_cases(client: TestClient, headers: dict[str, str], data: dict[str, int]) -> tuple[str, str]:
    first = case_payload(data)
    first.update({"subject": "Approval condition violation in laboratory", "description": "The institution has not complied with approval conditions for laboratory equipment.", "external_reference": "REF-OVERLAP"})
    second = case_payload(data)
    second.update({"subject": "Laboratory approval condition violation", "description": "The institution has not complied with approval conditions for laboratory equipment.", "external_reference": "REF-OVERLAP", "current_bureau_id": data["pgrc"]})
    return client.post("/api/cases", json=first, headers=headers).json()["case_id"], client.post("/api/cases", json=second, headers=headers).json()["case_id"]


def test_overlap_review_alert_dedup_and_audit(client, setup_data):
    headers = token(client, "admin@test.example.com")
    create_related_cases(client, headers, setup_data)
    assert client.post("/api/overlaps/refresh", headers=headers).status_code == 200
    overlaps = client.get("/api/overlaps", headers=headers).json()
    candidate = next(item for item in overlaps if {item["case_low_id"], item["case_high_id"]})
    assert candidate["identity_match"] is True
    assert candidate["similarity_score"] >= 55
    assert any("external reference" in reason.casefold() for reason in candidate["reasons"])
    review = client.post(f"/api/overlaps/{candidate['id']}/review", headers=headers, json={"status": "Confirmed Related", "remarks": "Coordinate fictional case handling"})
    assert review.status_code == 200 and review.json()["status"] == "Confirmed Related"
    first_monitor = client.post("/api/monitoring/run", headers=headers).json()
    second_monitor = client.post("/api/monitoring/run", headers=headers).json()
    alerts = client.get("/api/alerts", headers=headers).json()
    assert first_monitor["overlaps_refreshed"] >= 0 and second_monitor["overlaps_refreshed"] >= 0
    assert len({item["id"] for item in alerts}) == len(alerts)
    assert client.post(f"/api/alerts/{alerts[0]['id']}/acknowledge", headers=headers).status_code == 200
    audit = client.get("/api/audit-events", headers=headers)
    assert audit.status_code == 200
    assert any(item["action"] == "overlap_reviewed" for item in audit.json())
    assert client.get("/api/audit-events", headers=token(client, "rb@test.example.com")).status_code == 403


def test_overlap_does_not_cross_institutions_and_reports_csv_permissions(client, setup_data):
    headers = token(client, "admin@test.example.com")
    first = case_payload(setup_data)
    first.update({"subject": "Same exact narrative", "description": "The same exact synthetic narrative about facilities."})
    other = case_payload({**setup_data, "institution": setup_data["south_institution"]})
    other.update({"subject": "Same exact narrative", "description": "The same exact synthetic narrative about facilities."})
    assert client.post("/api/cases", json=first, headers=headers).status_code == 201
    assert client.post("/api/cases", json=other, headers=headers).status_code == 201
    client.post("/api/overlaps/refresh", headers=headers)
    assert client.get("/api/overlaps", headers=headers).json() == []
    summary = client.get("/api/analytics/summary", headers=headers)
    assert summary.status_code == 200 and summary.json()["total_received"] == 2
    export = client.get("/api/analytics/cases.csv", headers=headers)
    assert export.status_code == 200 and "Case ID" in export.text
    north_export = client.get("/api/analytics/cases.csv", headers=token(client, "north@test.example.com"))
    assert north_export.status_code == 200 and "South Test Institute" not in north_export.text


def test_filtered_analytics_and_safe_csv_exports(client, setup_data):
    headers = token(client, "admin@test.example.com")
    payload = case_payload(setup_data)
    payload.update({"subject": "=formula-like synthetic subject", "description": "Synthetic description for filtered reporting.", "category": "Formula"})
    assert client.post("/api/cases", json=payload, headers=headers).status_code == 201
    filtered = client.get("/api/analytics/summary", params={"region": "North", "category": "Formula"}, headers=headers)
    assert filtered.status_code == 200
    report = filtered.json()
    assert report["total_received"] == 1
    assert report["monthly_trend"] and report["quarterly_trend"]
    csv_export = client.get("/api/analytics/institutions/1/history.csv", headers=headers)
    assert "'=formula-like synthetic subject" in csv_export.text
    for endpoint in ("cases.csv", "bureau-summary.csv", "region-summary.csv", "ageing.csv", "overlaps.csv"):
        response = client.get(f"/api/analytics/{endpoint}", headers=headers)
        assert response.status_code == 200
