import pytest
from event_extraction.models import (
    ExecutionEvent,
    ExtractionResult,
    SourceType,
    ClarificationRequest,
    DuplicateGroup,
)


def test_execution_event_defaults():
    event = ExecutionEvent(
        source_id="test",
        source_type=SourceType.DAILY_REPORT,
        raw_text="test text",
        description="test",
        status="completed",
    )
    assert event.event_id.startswith("EVT-")
    assert event.source_id == "test"
    assert event.discipline is None
    assert event.asset is None
    assert event.extraction_confidence == 0.0


def test_execution_event_full():
    event = ExecutionEvent(
        event_id="EVT-001",
        source_id="DPR-2026-08-30",
        source_type=SourceType.DAILY_REPORT,
        raw_text="Line 24 spool erection completed",
        description="Spool erection completed for Line 24",
        discipline="piping",
        activity_type="erection",
        asset="Line 24",
        location="Unit 4",
        status="completed",
        event_date="2026-08-30",
        extraction_confidence=0.94,
    )
    assert event.event_id == "EVT-001"
    assert event.discipline == "piping"
    assert event.asset == "Line 24"


def test_extraction_result():
    result = ExtractionResult(
        events=[],
        source_id="test",
        source_type=SourceType.DAILY_REPORT,
    )
    assert result.events == []
    assert result.warnings == []


def test_clarification_request():
    event = ExecutionEvent(
        source_id="test",
        source_type=SourceType.SUPERVISOR_MESSAGE,
        raw_text="Erection done",
        description="Erection done",
        status="completed",
    )
    req = ClarificationRequest(
        event=event,
        missing_fields=["asset"],
        question="Which line?",
        options=["Line 24", "Line 25"],
    )
    assert len(req.options) == 2


def test_duplicate_group():
    group = DuplicateGroup(
        primary_event_id="EVT-001",
        duplicate_event_ids=["EVT-002", "EVT-003"],
        similarity_score=0.92,
    )
    assert len(group.duplicate_event_ids) == 2
