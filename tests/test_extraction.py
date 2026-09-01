import pytest
from datetime import date

from event_extraction.models import ExecutionEvent, SourceType
from event_extraction.extraction.rule_based import RuleBasedExtractor


class TestRuleBasedExtractor:
    def setup_method(self):
        self.extractor = RuleBasedExtractor()

    def _make_event(self, text: str, discipline: str = None) -> ExecutionEvent:
        return ExecutionEvent(
            source_id="test",
            source_type=SourceType.DAILY_REPORT,
            raw_text=text,
            description=text,
            discipline=discipline,
            status="unknown",
        )

    def test_line_24_erection_completed(self):
        event = self._make_event("Line 24 spool erection completed.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.asset == "Line 24"
        assert result.activity_type == "erection"
        assert result.status == "completed"
        assert result.discipline == "piping"

    def test_welding_in_progress(self):
        event = self._make_event("Welding of Line 25 joints is currently in progress.")
        result = self.extractor.extract(event, date(2026, 8, 28))
        assert result.asset == "Line 25"
        assert result.activity_type == "welding"
        assert result.status == "in_progress"

    def test_cable_tray_installation(self):
        event = self._make_event("Cable tray installation in Area B has been completed.")
        result = self.extractor.extract(event, date(2026, 8, 28))
        assert result.activity_type == "installation"
        assert result.location == "Area B"
        assert result.status == "completed"
        assert result.discipline == "electrical"

    def test_valve_installed(self):
        event = self._make_event("Valve V-302 installed on Line 25 today.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.asset in ("V-302", "Line 25")
        assert result.status == "completed"

    def test_pump_alignment(self):
        event = self._make_event("Pump P-101 alignment completed and signed off.")
        result = self.extractor.extract(event, date(2026, 8, 29))
        assert result.asset == "P-101"
        assert result.activity_type == "alignment"
        assert result.status == "completed"

    def test_hydrotest(self):
        event = self._make_event("Hydrotesting for line 24 completed successfully.")
        result = self.extractor.extract(event, date(2026, 8, 29))
        assert result.activity_type == "hydrotest"
        assert result.status == "completed"

    def test_blocked_status(self):
        event = self._make_event("Loop check for FT-101 could not be done. Calibration kit arrived but one instrument found faulty.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.status == "blocked"
        assert result.asset == "FT-101"

    def test_pending_material(self):
        event = self._make_event("Valve V-301 still pending. Material not yet received.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.status in ("not_started", "blocked")
        assert result.asset == "V-301"

    def test_quantity_extraction(self):
        event = self._make_event("Approximately 120 metres of cable pulled.")
        result = self.extractor.extract(event, date(2026, 8, 28))
        assert result.quantity == 120.0
        assert result.unit == "metres"

    def test_compressor_set(self):
        event = self._make_event("Compressor K-201 set on foundation.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.asset == "K-201"
        assert result.discipline == "mechanical"

    def test_mcc_panel(self):
        event = self._make_event("MCC panel M-301 installation done at Substation.")
        result = self.extractor.extract(event, date(2026, 8, 29))
        assert result.asset == "M-301"
        assert result.location == "Substation"
        assert result.status == "completed"

    def test_csv_row_data(self):
        event = self._make_event("spool erection Line 24")
        event.discipline = "piping"
        event.status = "completed"
        result = self.extractor.extract(event, date(2026, 8, 28))
        assert result.asset == "Line 24"
        assert result.activity_type == "erection"

    def test_abbreviation_l25(self):
        event = self._make_event("welding L25 finished")
        event.discipline = "piping"
        event.status = "completed"
        result = self.extractor.extract(event, date(2026, 8, 29))
        assert result.asset == "Line 25"
        assert result.activity_type == "welding"

    def test_ambiguous_text_low_extraction(self):
        event = self._make_event("Pipe work done in Unit 4.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.status == "completed"
        assert result.location == "Unit 4"
        assert result.asset is None

    def test_very_ambiguous(self):
        event = self._make_event("Erection completed today.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.status == "completed"
        assert result.activity_type == "erection"
        assert result.asset is None

    def test_relative_date_yesterday(self):
        event = self._make_event("Excavation completed yesterday.")
        result = self.extractor.extract(event, date(2026, 8, 28))
        assert result.event_date == "2026-08-27"

    def test_event_type_start(self):
        event = self._make_event("Cable tray installation started in Area B.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.event_type == "START"

    def test_event_type_complete(self):
        event = self._make_event("Line 24 insulation completed.")
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.event_type == "COMPLETE"

    def test_event_type_progress(self):
        event = self._make_event("Line 25 welding is in progress.")
        result = self.extractor.extract(event, date(2026, 8, 28))
        assert result.event_type == "PROGRESS"

    def test_preserves_raw_text(self):
        raw = "Line 24 spool erection completed at Unit 4."
        event = self._make_event(raw)
        result = self.extractor.extract(event, date(2026, 8, 30))
        assert result.raw_text == raw
