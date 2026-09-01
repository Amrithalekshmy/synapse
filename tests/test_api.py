import pytest
from fastapi.testclient import TestClient

from event_extraction.main import app

client = TestClient(app)


class TestAPI:
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["module"] == "event_extraction"

    def test_extract_text(self):
        response = client.post("/events/extract/text", json={
            "text": "Line 24 spool erection completed today at Unit 4.",
            "source_id": "test_supervisor",
            "reference_date": "2026-08-30",
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) >= 1
        event = data["events"][0]
        assert event["asset"] == "Line 24"
        assert event["status"] == "completed"
        assert event["raw_text"] == "Line 24 spool erection completed today at Unit 4."

    def test_extract_ambiguous_text(self):
        response = client.post("/events/extract/text", json={
            "text": "Pipe work done in Unit 4.",
        })
        assert response.status_code == 200
        data = response.json()
        event = data["events"][0]
        assert event["asset"] is None
        assert event["status"] == "completed"
        assert event["location"] == "Unit 4"

    def test_list_events_after_extraction(self):
        client.post("/events/extract/text", json={
            "text": "Cable tray installation in Area B completed.",
            "source_id": "list_test",
        })
        response = client.get("/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    def test_get_events_by_source(self):
        client.post("/events/extract/text", json={
            "text": "Pump P-101 alignment done.",
            "source_id": "source_test_123",
        })
        response = client.get("/events/source_test_123")
        assert response.status_code == 200
        data = response.json()
        assert data["source_id"] == "source_test_123"

    def test_get_events_not_found(self):
        response = client.get("/events/nonexistent_source")
        assert response.status_code == 404

    def test_extract_file_upload(self):
        from pathlib import Path
        csv_path = Path(__file__).resolve().parent.parent / "data" / "discipline_report_piping.csv"
        if not csv_path.exists():
            pytest.skip("piping CSV not found")
        with open(csv_path, "rb") as f:
            response = client.post(
                "/events/extract",
                files={"file": ("discipline_report_piping.csv", f, "text/csv")},
            )
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) > 0

    def test_clarification_requests(self):
        client.post("/events/extract/text", json={
            "text": "Erection completed today.",
            "source_id": "clarify_test",
        })
        response = client.post("/events/clarification-requests")
        assert response.status_code == 200

    def test_find_duplicates(self):
        client.post("/events/extract/text", json={
            "text": "Line 24 erection done.",
            "source_id": "dup_test_1",
        })
        client.post("/events/extract/text", json={
            "text": "Line 24 spool erection completed.",
            "source_id": "dup_test_2",
        })
        response = client.post("/events/duplicates")
        assert response.status_code == 200

    def test_invalid_date_format(self):
        response = client.post("/events/extract/text", json={
            "text": "test",
            "reference_date": "not-a-date",
        })
        assert response.status_code == 400
