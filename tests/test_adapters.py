from datetime import date

import pytest

from progress_analytics.adapters import match_result_to_event


def test_match_result_is_converted():
    result = {
        "event_id": "EVT-001",
        "date": "2026-08-24",
        "matched_activity_id": "A-1040",
        "confidence": 0.91,
        "decision": "auto_linked",
        "status_hint": "completed",
        "original_text": "Pipe installation completed in Unit 4",
    }

    event = match_result_to_event(result)

    assert event.event_id == "EVT-001"
    assert event.activity_id == "A-1040"
    assert event.event_date == date(2026, 8, 24)
    assert event.confidence == 0.91
    assert event.decision == "auto_linked"


def test_unmatched_result_is_rejected():
    result = {
        "event_id": "EVT-002",
        "date": "2026-08-24",
        "matched_activity_id": None,
        "confidence": 0.42,
        "decision": "clarification_needed",
        "status_hint": "unknown",
        "original_text": "Work happening somewhere",
    }

    with pytest.raises(ValueError):
        match_result_to_event(result)