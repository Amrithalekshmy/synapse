"""
Unit and Integration Tests for SYNAPSE Schedule Parser (Yazeen's Module).
Covers format detection, Primavera P6 XER, MS Project XML, synthetic CSV,
WBS hierarchy reconstruction, L5/L6 filtering, data-quality auditing,
and seamless handoff to Amritha's matching engine.
"""

import os
import unittest
from pathlib import Path

from schedule_parser import (
    ScheduleParser,
    detect_format,
    ScheduleFormat,
    ScheduleActivity,
    QualitySeverity,
)
from schedule_parser.normalization import (
    normalize_discipline,
    normalize_location,
    normalize_date,
    normalize_status,
    build_search_text,
)
from schedule_parser.wbs import WBSTree
from schedule_parser.filtering import filter_activities


class TestScheduleParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent
        cls.fixtures_dir = cls.repo_root / "tests" / "fixtures"
        cls.sample_csv = cls.repo_root / "data" / "schedule.csv"
        cls.sample_xer = cls.fixtures_dir / "sample_primavera.xer"
        cls.sample_msproject = cls.fixtures_dir / "sample_msproject.xml"
        cls.sample_corrupted = cls.fixtures_dir / "sample_corrupted.csv"

    def setUp(self):
        self.parser = ScheduleParser()

    # ------------------------------------------------------------------
    # 1. FORMAT DETECTION
    # ------------------------------------------------------------------

    def test_format_detection(self):
        fmt, _ = detect_format(str(self.sample_csv))
        self.assertEqual(fmt, ScheduleFormat.SYNTHETIC_CSV)

        fmt, _ = detect_format(str(self.sample_xer))
        self.assertEqual(fmt, ScheduleFormat.PRIMAVERA_XER)

        fmt, _ = detect_format(str(self.sample_msproject))
        self.assertEqual(fmt, ScheduleFormat.MSPROJECT_XML)

    # ------------------------------------------------------------------
    # 2. SYNTHETIC CSV SCHEDULE PARSING (synapse/data/schedule.csv)
    # ------------------------------------------------------------------

    def test_parse_synthetic_csv(self):
        res = self.parser.parse(str(self.sample_csv))

        self.assertEqual(res.format_detected, "synthetic_csv")
        self.assertEqual(res.total_activities_read, 41)
        self.assertEqual(res.l5_l6_activities_count, 41)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.quality_report.error_count, 0)

        # Check first activity: PIP-001
        first = res.activities[0]
        self.assertEqual(first.activity_id, "PIP-001")
        self.assertEqual(first.activity_name, "Fabricate spool S-101 for Line 24")
        self.assertEqual(first.discipline, "piping")
        self.assertEqual(first.location, "Fabrication Yard")
        self.assertEqual(first.planned_start, "2026-08-01")
        self.assertEqual(first.planned_finish, "2026-08-05")
        self.assertEqual(first.duration_days, 5)
        self.assertIn("PIP-002", first.successors)

        # Check search text enrichment
        self.assertIn("piping", first.search_text.lower())
        self.assertIn("fabrication yard", first.search_text.lower())
        self.assertIn("line 24", first.search_text.lower())

    # ------------------------------------------------------------------
    # 3. PRIMAVERA P6 XER PARSING
    # ------------------------------------------------------------------

    def test_parse_primavera_xer(self):
        res = self.parser.parse(str(self.sample_xer))

        self.assertEqual(res.format_detected, "primavera_xer")
        self.assertEqual(res.project_id, "OIL-IND-EPC")
        self.assertEqual(len(res.activities), 4)

        # Activity ID preservation (Rule 1)
        act_ids = [a.activity_id for a in res.activities]
        self.assertIn("PIP-001", act_ids)
        self.assertIn("PIP-002", act_ids)
        self.assertIn("ELE-001", act_ids)

        # Check WBS path reconstruction
        pip01 = next(a for a in res.activities if a.activity_id == "PIP-001")
        self.assertIn("Unit 4 Plant Area", pip01.wbs_path)
        self.assertIn("Unit 4 Piping Work Package", pip01.wbs_path)

        # Check separation of actual dates vs planned dates (Rule 4)
        self.assertEqual(pip01.planned_start, "2026-08-01")
        self.assertEqual(pip01.actual_start, "2026-08-01")
        self.assertEqual(pip01.actual_finish, "2026-08-05")

        # Check predecessor relationship resolution
        pip02 = next(a for a in res.activities if a.activity_id == "PIP-002")
        self.assertIn("PIP-001", pip02.predecessors)

    # ------------------------------------------------------------------
    # 4. MICROSOFT PROJECT XML PARSING
    # ------------------------------------------------------------------

    def test_parse_msproject_xml(self):
        res = self.parser.parse(str(self.sample_msproject))

        self.assertEqual(res.format_detected, "msproject_xml")
        # Verify L1 and L2 summary tasks were filtered from execution activities
        self.assertEqual(res.filtered_summary_count, 2)
        self.assertEqual(res.l5_l6_activities_count, 3)

        act_ids = [a.activity_id for a in res.activities]
        self.assertIn("PIP-001", act_ids)
        self.assertIn("PIP-002", act_ids)
        self.assertIn("ELE-001", act_ids)

        # Predecessor mapping from UID to Activity ID
        pip02 = next(a for a in res.activities if a.activity_id == "PIP-002")
        self.assertIn("PIP-001", pip02.predecessors)

    # ------------------------------------------------------------------
    # 5. DATA QUALITY CHECKS (7-Rule Validation Engine)
    # ------------------------------------------------------------------

    def test_data_quality_audit(self):
        res = self.parser.parse(str(self.sample_corrupted))

        self.assertFalse(res.is_valid)
        report = res.quality_report
        issue_types = [issue.issue_type for issue in report.issues]

        # 1. Missing ID
        self.assertIn("missing_id", issue_types)

        # 2. Duplicate ID
        self.assertIn("duplicate_id", issue_types)

        # 3. Invalid dates
        self.assertIn("invalid_date", issue_types)

        # 4. Finish before start
        self.assertIn("finish_before_start", issue_types)

        # 5. Missing activity name
        self.assertIn("missing_name", issue_types)

        # 6. Missing WBS context
        self.assertIn("missing_wbs", issue_types)

        # 7. Non-L5/L6 rows
        self.assertIn("non_l5_l6", issue_types)

    # ------------------------------------------------------------------
    # 6. FIELD NORMALIZATION & SEARCH ENRICHMENT
    # ------------------------------------------------------------------

    def test_normalization_rules(self):
        # Disciplines
        self.assertEqual(normalize_discipline("Piping Work"), "piping")
        self.assertEqual(normalize_discipline("ELEC"), "electrical")
        self.assertEqual(normalize_discipline("Earthworks"), "civil")
        self.assertEqual(normalize_discipline("Rotating Equipment"), "mechanical")
        self.assertEqual(normalize_discipline("Instrumentation & Control"), "instrumentation")

        # Locations
        self.assertEqual(normalize_location("unit-4"), "Unit 4")
        self.assertEqual(normalize_location("area b"), "Area B")
        self.assertEqual(normalize_location("fab yard"), "Fabrication Yard")

        # Dates
        self.assertEqual(normalize_date("2026-08-20 00:00:00"), "2026-08-20")
        self.assertEqual(normalize_date("2026-08-20T08:00:00"), "2026-08-20")
        self.assertEqual(normalize_date("20/08/2026"), "2026-08-20")

        # Search context builder
        search = build_search_text(
            activity_name="Erect Line 24-XX spool S-101",
            discipline="piping",
            location="Unit 4",
            wbs_path="Project > Unit 4 > Piping",
        )
        self.assertIn("Line 24", search)
        self.assertIn("S-101", search)
        self.assertIn("piping", search)
        self.assertIn("Unit 4", search)

    # ------------------------------------------------------------------
    # 7. WBS HIERARCHY RECONSTRUCTION & CONTEXT INHERITANCE
    # ------------------------------------------------------------------

    def test_wbs_inheritance(self):
        tree = WBSTree()
        tree.add_node("ROOT", "ROOT", "Oil India Project", level=1)
        tree.add_node("U4", "U4", "Unit 4", parent_wbs_id="ROOT", level=2)
        tree.add_node("U4-PIP", "PIP", "Unit 4 Piping Systems", parent_wbs_id="U4", level=3)
        tree.build_hierarchy()

        # Child activity in U4-PIP with no explicit location/discipline
        path, disc, loc, lvl = tree.get_context_for_activity("U4-PIP")
        self.assertEqual(path, "Oil India Project > Unit 4 > Unit 4 Piping Systems")
        self.assertEqual(disc, "piping")
        self.assertEqual(loc, "Unit 4")
        self.assertEqual(lvl, 3)

    # ------------------------------------------------------------------
    # 8. AMRITHA MATCHING ENGINE INTEGRATION HANDOFF
    # ------------------------------------------------------------------

    def test_amritha_matching_engine_handoff(self):
        """
        Verify that Amritha's SynapseMatchingEngine accepts Yazeen's parsed
        activities directly via engine.load_activities().
        """
        try:
            from amrita.matcher import SynapseMatchingEngine
        except ImportError:
            self.skipTest("pandas/scikit-learn required for Amritha matcher integration test")
        parse_result = self.parser.parse(str(self.sample_csv))
        amritha_activities = parse_result.to_amritha_format()

        self.assertEqual(len(amritha_activities), 41)

        # Load into Amritha's matching engine
        engine = SynapseMatchingEngine()
        engine.load_activities(amritha_activities)

        self.assertEqual(len(engine.activities), 41)
        self.assertIsNotNone(engine.activity_embeddings)

        # Test query match through Amritha's engine
        match = engine.match_event(
            event_text="Line 24 spool erection completed today at Unit 4",
            discipline="piping",
            location="Unit 4",
        )

        self.assertIsNotNone(match)
        self.assertEqual(match["matched_activity_id"], "PIP-002")
        self.assertGreaterEqual(match["confidence"], 0.85)


if __name__ == "__main__":
    unittest.main()
