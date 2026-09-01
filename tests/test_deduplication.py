import pytest

from event_extraction.models import ExecutionEvent, SourceType
from event_extraction.deduplication import compute_similarity, find_duplicates


class TestDeduplication:
    def _make_event(self, desc: str, **kwargs) -> ExecutionEvent:
        defaults = {
            "source_id": "test",
            "source_type": SourceType.DAILY_REPORT,
            "raw_text": desc,
            "description": desc,
            "status": "completed",
        }
        defaults.update(kwargs)
        return ExecutionEvent(**defaults)

    def test_identical_events_high_similarity(self):
        a = self._make_event(
            "Line 24 spool erection completed",
            discipline="piping",
            asset="Line 24",
            activity_type="erection",
            event_date="2026-08-28",
        )
        b = self._make_event(
            "Line 24 spool erection completed",
            discipline="piping",
            asset="Line 24",
            activity_type="erection",
            event_date="2026-08-28",
        )
        sim = compute_similarity(a, b)
        assert sim >= 0.90

    def test_same_event_different_wording(self):
        a = self._make_event(
            "Line 24 spool erection completed",
            discipline="piping",
            asset="Line 24",
            activity_type="erection",
        )
        b = self._make_event(
            "spool erection Line 24 done",
            discipline="piping",
            asset="Line 24",
            activity_type="erection",
        )
        sim = compute_similarity(a, b)
        assert sim >= 0.70

    def test_different_events_low_similarity(self):
        a = self._make_event(
            "Line 24 spool erection completed",
            discipline="piping",
            asset="Line 24",
            activity_type="erection",
        )
        b = self._make_event(
            "Cable tray installation in Area B",
            discipline="electrical",
            asset="CT-A",
            activity_type="installation",
        )
        sim = compute_similarity(a, b)
        assert sim < 0.50

    def test_find_duplicates(self):
        events = [
            self._make_event(
                "Line 24 erection completed",
                discipline="piping",
                asset="Line 24",
                activity_type="erection",
                event_date="2026-08-28",
            ),
            self._make_event(
                "spool erection Line 24 done",
                discipline="piping",
                asset="Line 24",
                activity_type="erection",
                event_date="2026-08-28",
            ),
            self._make_event(
                "Cable tray done in Area B",
                discipline="electrical",
                asset="CT-A",
                activity_type="installation",
            ),
        ]
        groups = find_duplicates(events, threshold=0.70)
        assert len(groups) >= 1
        assert len(groups[0].duplicate_event_ids) >= 1

    def test_no_duplicates_when_different(self):
        events = [
            self._make_event("Line 24 erection", asset="Line 24"),
            self._make_event("Cable tray Area B", asset="CT-A"),
            self._make_event("Pump P-101 set", asset="P-101"),
        ]
        groups = find_duplicates(events, threshold=0.80)
        assert len(groups) == 0
