import pytest

from event_extraction.models import ExecutionEvent, SourceType
from event_extraction.confidence import score_confidence


class TestConfidenceScoring:
    def _make_event(self, **kwargs) -> ExecutionEvent:
        defaults = {
            "source_id": "test",
            "source_type": SourceType.DAILY_REPORT,
            "raw_text": "test",
            "description": "test",
            "status": "unknown",
        }
        defaults.update(kwargs)
        return ExecutionEvent(**defaults)

    def test_full_extraction_high_confidence(self):
        event = self._make_event(
            description="Spool erection completed for Line 24 at Unit 4",
            discipline="piping",
            activity_type="erection",
            asset="Line 24",
            location="Unit 4",
            status="completed",
            event_date="2026-08-30",
            quantity=4.0,
            unit="spools",
        )
        score = score_confidence(event)
        assert score >= 0.85

    def test_minimal_extraction_low_confidence(self):
        event = self._make_event(status="completed")
        score = score_confidence(event)
        assert score < 0.40

    def test_missing_asset_reduces_confidence(self):
        full = self._make_event(
            description="Erection completed for Line 24",
            discipline="piping",
            activity_type="erection",
            asset="Line 24",
            status="completed",
        )
        no_asset = self._make_event(
            description="Erection completed",
            discipline="piping",
            activity_type="erection",
            status="completed",
        )
        assert score_confidence(full) > score_confidence(no_asset)

    def test_structured_source_bonus(self):
        csv_event = self._make_event(
            source_type=SourceType.DISCIPLINE_REPORT,
            discipline="piping",
            status="completed",
        )
        text_event = self._make_event(
            source_type=SourceType.SUPERVISOR_MESSAGE,
            discipline="piping",
            status="completed",
        )
        assert score_confidence(csv_event) > score_confidence(text_event)

    def test_confidence_capped_below_1(self):
        event = self._make_event(
            description="Full detailed description here for testing",
            discipline="piping",
            activity_type="erection",
            asset="Line 24",
            location="Unit 4",
            status="completed",
            event_date="2026-08-30",
            quantity=4.0,
            source_type=SourceType.DISCIPLINE_REPORT,
        )
        score = score_confidence(event)
        assert score <= 0.99
