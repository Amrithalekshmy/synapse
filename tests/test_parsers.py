import pytest
from pathlib import Path

from event_extraction.parsers.csv_parser import CSVParser
from event_extraction.parsers.text_parser import TextParser
from event_extraction.models import SourceType

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TestCSVParser:
    def setup_method(self):
        self.parser = CSVParser()

    def test_parse_piping_csv(self):
        csv_path = DATA_DIR / "discipline_report_piping.csv"
        if not csv_path.exists():
            pytest.skip("piping CSV not found")
        result = self.parser.parse(str(csv_path))
        assert len(result.events) > 0
        assert result.source_type == SourceType.DISCIPLINE_REPORT

    def test_parse_electrical_csv(self):
        csv_path = DATA_DIR / "discipline_report_electrical.csv"
        if not csv_path.exists():
            pytest.skip("electrical CSV not found")
        result = self.parser.parse(str(csv_path))
        assert len(result.events) > 0

    def test_events_have_required_fields(self):
        csv_path = DATA_DIR / "discipline_report_piping.csv"
        if not csv_path.exists():
            pytest.skip("piping CSV not found")
        result = self.parser.parse(str(csv_path))
        for event in result.events:
            assert event.raw_text
            assert event.source_id
            assert event.event_id.startswith("EVT-")

    def test_csv_extracts_discipline(self):
        csv_path = DATA_DIR / "discipline_report_piping.csv"
        if not csv_path.exists():
            pytest.skip("piping CSV not found")
        result = self.parser.parse(str(csv_path))
        for event in result.events:
            assert event.discipline == "piping"


class TestTextParser:
    def setup_method(self):
        self.parser = TextParser()

    def test_parse_dpr_28(self):
        txt_path = DATA_DIR / "daily_reports" / "DPR_2026_08_28.txt"
        if not txt_path.exists():
            pytest.skip("DPR not found")
        result = self.parser.parse_file(str(txt_path))
        assert len(result.events) > 0
        assert result.source_type == SourceType.DAILY_REPORT

    def test_parse_dpr_30(self):
        txt_path = DATA_DIR / "daily_reports" / "DPR_2026_08_30.txt"
        if not txt_path.exists():
            pytest.skip("DPR not found")
        result = self.parser.parse_file(str(txt_path))
        assert len(result.events) > 0

    def test_extracts_report_date(self):
        text = "Date: 30 August 2026\n=== PIPING ===\nLine 24 done."
        result = self.parser.parse(text)
        assert any(e.event_date == "2026-08-30" for e in result.events)

    def test_splits_disciplines(self):
        text = (
            "Date: 30 August 2026\n"
            "=== PIPING ===\nLine 24 completed.\n"
            "=== ELECTRICAL ===\nCable tray done.\n"
        )
        result = self.parser.parse(text)
        disciplines = {e.discipline for e in result.events if e.discipline}
        assert "piping" in disciplines
        assert "electrical" in disciplines

    def test_skips_meta_lines(self):
        text = (
            "Daily Progress Report\n"
            "Project: Test\n"
            "Date: 30 August 2026\n"
            "Prepared by: Engineer\n"
            "=== PIPING ===\nLine 24 done.\n"
        )
        result = self.parser.parse(text)
        for event in result.events:
            assert "daily progress report" not in event.raw_text.lower()
            assert "project:" not in event.raw_text.lower()

    def test_multiple_sentences_per_section(self):
        text = (
            "=== PIPING ===\n"
            "Line 24 completed. Line 25 welding in progress.\n"
        )
        result = self.parser.parse(text)
        assert len(result.events) >= 2
