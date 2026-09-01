import pytest
from datetime import date

from event_extraction.normalization import (
    normalize_status,
    normalize_activity_type,
    infer_discipline,
    extract_assets,
    extract_location,
    extract_quantity,
    normalize_date,
    normalize_asset_identifier,
)


class TestNormalizeStatus:
    def test_completed_variants(self):
        assert normalize_status("completed") == "completed"
        assert normalize_status("complete") == "completed"
        assert normalize_status("done") == "completed"
        assert normalize_status("finished") == "completed"
        assert normalize_status("Activity is done") == "completed"

    def test_started_variants(self):
        assert normalize_status("started") == "started"
        assert normalize_status("begun") == "started"
        assert normalize_status("commenced") == "started"

    def test_in_progress_variants(self):
        assert normalize_status("in progress") == "in_progress"
        assert normalize_status("ongoing") == "in_progress"

    def test_blocked_variants(self):
        assert normalize_status("could not be done") == "blocked"
        assert normalize_status("found faulty") == "blocked"

    def test_not_started_variants(self):
        assert normalize_status("pending") == "not_started"
        assert normalize_status("not yet received") == "not_started"

    def test_unknown(self):
        assert normalize_status("some random text") is None


class TestNormalizeActivityType:
    def test_erection(self):
        assert normalize_activity_type("erect") == "erection"
        assert normalize_activity_type("erected") == "erection"
        assert normalize_activity_type("erection") == "erection"
        assert normalize_activity_type("spool erection done") == "erection"

    def test_welding(self):
        assert normalize_activity_type("welding of joints") == "welding"
        assert normalize_activity_type("welded") == "welding"

    def test_installation(self):
        assert normalize_activity_type("installed") == "installation"
        assert normalize_activity_type("installation") == "installation"

    def test_hydrotest(self):
        assert normalize_activity_type("hydrotest") == "hydrotest"
        assert normalize_activity_type("hydrotesting") == "hydrotest"

    def test_loop_check(self):
        assert normalize_activity_type("loop check completed") == "loop_check"


class TestInferDiscipline:
    def test_piping(self):
        assert infer_discipline("spool erection for pipe line") == "piping"
        assert infer_discipline("valve V-301 installed") == "piping"

    def test_electrical(self):
        assert infer_discipline("cable tray installation") == "electrical"
        assert infer_discipline("MCC panel M-301 done") == "electrical"

    def test_civil(self):
        assert infer_discipline("concrete pouring for foundation") == "civil"
        assert infer_discipline("excavation completed") == "civil"

    def test_instrumentation(self):
        assert infer_discipline("flow transmitter FT-101 installed") == "instrumentation"
        assert infer_discipline("loop check done") == "instrumentation"

    def test_mechanical(self):
        assert infer_discipline("pump alignment completed") == "mechanical"
        assert infer_discipline("compressor set on foundation") == "mechanical"


class TestExtractAssets:
    def test_line_identifiers(self):
        assert "Line 24" in extract_assets("Line 24 spool erection")
        assert "Line 24" in extract_assets("L24 spool done")
        assert "Line 25" in extract_assets("L-25 welding finished")

    def test_equipment_identifiers(self):
        assert "V-301" in extract_assets("Valve V-301 installed")
        assert "P-101" in extract_assets("Pump P-101 aligned")
        assert "K-201" in extract_assets("Compressor K-201 set")
        assert "FT-101" in extract_assets("FT-101 installed")

    def test_multiple_assets(self):
        assets = extract_assets("FT-101 and PG-101 loop check")
        assert "FT-101" in assets
        assert "PG-101" in assets

    def test_no_assets(self):
        assert extract_assets("general work done") == []


class TestExtractLocation:
    def test_unit(self):
        assert extract_location("work in Unit 4") == "Unit 4"

    def test_area(self):
        assert extract_location("cable tray in Area B") == "Area B"

    def test_substation(self):
        assert extract_location("panel at Substation") == "Substation"

    def test_no_location(self):
        assert extract_location("work completed") is None


class TestExtractQuantity:
    def test_metres(self):
        q, u = extract_quantity("120 metres pulled")
        assert q == 120.0
        assert u == "metres"

    def test_spools(self):
        q, u = extract_quantity("4 spools erected")
        assert q == 4.0
        assert u == "spools"

    def test_percentage(self):
        q, u = extract_quantity("40%")
        assert q == 40.0
        assert u == "%"

    def test_fraction(self):
        q, u = extract_quantity("3 of 6 joints")
        assert q == 3.0
        assert u == "of 6"

    def test_no_quantity(self):
        q, u = extract_quantity("work completed")
        assert q is None


class TestNormalizeDate:
    def test_today(self):
        ref = date(2026, 8, 30)
        assert normalize_date("completed today", ref) == "2026-08-30"

    def test_yesterday(self):
        ref = date(2026, 8, 30)
        assert normalize_date("completed yesterday", ref) == "2026-08-29"

    def test_tomorrow(self):
        ref = date(2026, 8, 30)
        assert normalize_date("will start tomorrow", ref) == "2026-08-31"

    def test_explicit_date(self):
        result = normalize_date("completed on 30/08/2026")
        assert result == "2026-08-30"


class TestNormalizeAssetIdentifier:
    def test_l_prefix(self):
        assert normalize_asset_identifier("L24") == "Line 24"
        assert normalize_asset_identifier("L-25") == "Line 25"

    def test_already_normalized(self):
        assert normalize_asset_identifier("Line 24") == "Line 24"

    def test_equipment(self):
        assert normalize_asset_identifier("V-301") == "V-301"
