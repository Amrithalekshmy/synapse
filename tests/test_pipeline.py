import pytest
from pathlib import Path
from datetime import date

from event_extraction.pipeline import ExtractionPipeline
from event_extraction.models import SourceType

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TestPipeline:
    def setup_method(self):
        self.pipeline = ExtractionPipeline(use_llm=False)

    def test_process_piping_csv(self):
        csv_path = DATA_DIR / "discipline_report_piping.csv"
        if not csv_path.exists():
            pytest.skip("piping CSV not found")
        result = self.pipeline.process_file(str(csv_path))
        assert len(result.events) > 0
        for event in result.events:
            assert event.extraction_confidence > 0

    def test_process_dpr_text(self):
        txt_path = DATA_DIR / "daily_reports" / "DPR_2026_08_30.txt"
        if not txt_path.exists():
            pytest.skip("DPR not found")
        result = self.pipeline.process_file(str(txt_path))
        assert len(result.events) > 0
        assert result.processing_time_ms is not None

    def test_process_supervisor_text(self):
        result = self.pipeline.process_text(
            "Line 24 spool erection completed today at Unit 4.",
            source_id="supervisor_01",
            reference_date=date(2026, 8, 30),
        )
        assert len(result.events) == 1
        event = result.events[0]
        assert event.asset == "Line 24"
        assert event.status == "completed"
        assert event.discipline == "piping"
        assert event.extraction_confidence > 0.5

    def test_ambiguous_text(self):
        result = self.pipeline.process_text(
            "Erection completed today.",
            source_id="supervisor_02",
            reference_date=date(2026, 8, 30),
        )
        assert len(result.events) == 1
        event = result.events[0]
        assert event.asset is None
        assert event.status == "completed"
        assert event.extraction_confidence < 0.80

    def test_process_all_dprs(self):
        dpr_dir = DATA_DIR / "daily_reports"
        if not dpr_dir.exists():
            pytest.skip("DPR directory not found")
        total_events = 0
        for txt_file in sorted(dpr_dir.glob("*.txt")):
            result = self.pipeline.process_file(str(txt_file))
            total_events += len(result.events)
        assert total_events >= 15

    def test_process_all_csvs(self):
        total_events = 0
        for csv_file in sorted(DATA_DIR.glob("discipline_report_*.csv")):
            result = self.pipeline.process_file(str(csv_file))
            total_events += len(result.events)
        assert total_events >= 10

    def test_deduplication_across_sources(self):
        events = []
        for txt_file in sorted((DATA_DIR / "daily_reports").glob("*.txt")):
            result = self.pipeline.process_file(str(txt_file))
            events.extend(result.events)
        for csv_file in sorted(DATA_DIR.glob("discipline_report_*.csv")):
            result = self.pipeline.process_file(str(csv_file))
            events.extend(result.events)
        duplicates = self.pipeline.find_duplicates(events, threshold=0.80)
        assert isinstance(duplicates, list)

    def test_clarification_requests(self):
        result = self.pipeline.process_text("Erection completed today.")
        requests = self.pipeline.get_clarification_requests(result.events)
        assert len(requests) >= 1
        assert requests[0].missing_fields
        assert requests[0].question

    def test_unsupported_format(self):
        result = self.pipeline.process_file("fake_file.xyz")
        assert len(result.events) == 0
        assert len(result.warnings) > 0

    def test_event_has_source_traceability(self):
        result = self.pipeline.process_text(
            "Line 24 done",
            source_id="supervisor_msg_001",
        )
        event = result.events[0]
        assert event.source_id == "supervisor_msg_001"
        assert event.source_type == SourceType.SUPERVISOR_MESSAGE
        assert event.raw_text == "Line 24 done"
