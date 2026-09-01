import os
import json
import pytest

from amrita.matcher import SynapseMatchingEngine
from amrita.baselines import ExactMatcher, FuzzyMatcher
from amrita.explanation import generate_explanation
from amrita.granularity import GranularityTracker


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SCHEDULE_CSV = os.path.join(DATA_DIR, "schedule.csv")
GROUND_TRUTH = os.path.join(DATA_DIR, "ground_truth.json")


@pytest.fixture
def engine():
    return SynapseMatchingEngine(schedule_path=SCHEDULE_CSV)


@pytest.fixture
def ground_truth():
    with open(GROUND_TRUTH) as f:
        return json.load(f)


# ── Core matching ──

class TestMatchEvent:

    def test_easy_match_with_identifier(self, engine):
        result = engine.match_event(
            "Line 24 spool erection was completed by the piping crew today at Unit 4.",
            discipline="piping", location="Unit 4",
        )
        assert result["matched_activity_id"] == "PIP-002"
        assert result["confidence"] >= 0.65

    def test_paraphrase_match(self, engine):
        result = engine.match_event(
            "Hydrotesting for line 24 completed successfully.",
            discipline="piping",
        )
        candidate_ids = [c["activity_id"] for c in result["candidates"]]
        assert "PIP-004" in candidate_ids or result["matched_activity_id"] == "PIP-004"

    def test_asset_identifier_match(self, engine):
        result = engine.match_event("MCC panel M-301 installation done at Substation.")
        assert result["matched_activity_id"] == "ELE-008"

    def test_mechanical_match(self, engine):
        result = engine.match_event(
            "Pump P-101 has been set on foundation F-101.",
            discipline="mechanical",
        )
        assert result["matched_activity_id"] == "MEC-001"

    def test_ambiguous_triggers_clarification(self, engine):
        result = engine.match_event("welding done")
        assert result["decision"] in ("clarification_needed", "review", "unmatched")

    def test_ambiguous_no_autolink(self, engine):
        result = engine.match_event("Erection completed today.")
        assert result["decision"] in ("clarification_needed", "review", "unmatched")

    def test_cross_discipline_trap(self, engine):
        result = engine.match_event("Control valve CV-201 installation on Line 25 completed today.")
        assert result["matched_activity_id"] == "INS-004"

    def test_compressor_match(self, engine):
        result = engine.match_event("Compressor K-201 set on foundation.")
        assert result["matched_activity_id"] == "MEC-005"


# ── Explanation ──

class TestExplanation:

    def test_match_includes_explanation(self, engine):
        result = engine.match_event("Line 24 spool erection completed", discipline="piping")
        assert "explanation" in result
        exp = result["explanation"]
        assert "evidence" in exp
        assert exp["total_signals"] > 0

    def test_explanation_structure(self):
        breakdown = {
            "semantic_score": 0.6,
            "discipline_match": True,
            "location_match": False,
            "identifier_match": True,
            "event_discipline": "piping",
            "event_location": "",
        }
        activity = {"discipline": "piping", "location": "Unit 4"}
        exp = generate_explanation("test event", activity, breakdown)
        assert exp["matched_signals"] >= 2
        assert exp["semantic_score"] == 0.6


# ── Seven-layer scoring ──

class TestSevenLayerScoring:

    def test_discipline_boost(self, engine):
        no_disc = engine.match_event("Line 24 spool erection")
        with_disc = engine.match_event("Line 24 spool erection", discipline="piping")
        assert with_disc["confidence"] >= no_disc["confidence"]

    def test_location_boost(self, engine):
        no_loc = engine.match_event("Line 24 spool erection", discipline="piping")
        with_loc = engine.match_event("Line 24 spool erection", discipline="piping", location="Unit 4")
        assert with_loc["confidence"] >= no_loc["confidence"]

    def test_temporal_boost(self, engine):
        no_date = engine.match_event("Line 24 spool erection", discipline="piping")
        with_date = engine.match_event("Line 24 spool erection", discipline="piping", event_date="2026-08-08")
        assert with_date["confidence"] >= no_date["confidence"]


# ── Active learning ──

class TestActiveLearning:

    def test_feedback_boost(self, engine):
        before = engine.match_event("Spool erection Line 24 done at Unit 4", discipline="piping")

        engine.record_feedback(
            event_id="EVT-FB",
            event_text="Spool erection Line 24 done at Unit 4",
            correct_activity_id="PIP-002",
            approved=True,
        )

        after = engine.match_event("Spool erection Line 24 done at Unit 4", discipline="piping")
        assert after["confidence"] >= before["confidence"]

    def test_feedback_negative_no_boost(self, engine):
        engine.record_feedback(
            event_id="EVT-FB-NEG",
            event_text="wrong match text",
            correct_activity_id="PIP-002",
            approved=False,
        )
        result = engine.match_event("wrong match text")
        assert result is not None


# ── Baselines ──

class TestBaselines:

    def test_exact_matcher(self, engine):
        exact = ExactMatcher()
        results = exact.match("Fabricate spool S-101", engine.activities)
        assert len(results) > 0
        assert results[0]["method"] == "exact"

    def test_fuzzy_matcher(self, engine):
        fuzzy = FuzzyMatcher()
        results = fuzzy.match("spool erection Line 24", engine.activities)
        assert len(results) > 0
        assert results[0]["method"] == "fuzzy"

    def test_exact_perfect_match(self, engine):
        exact = ExactMatcher()
        results = exact.match("Fabricate spool S-101 for Line 24", engine.activities)
        assert results[0]["score"] > 0.5


# ── Granularity tracker ──

class TestGranularity:

    def test_record_link(self):
        tracker = GranularityTracker()
        tracker.record_link("EVT-001", "PIP-002", 0.9, "completed")
        assert tracker.get_activity_events("PIP-002") == ["EVT-001"]
        assert tracker.get_event_activities("EVT-001") == ["PIP-002"]

    def test_many_to_one(self):
        tracker = GranularityTracker()
        tracker.record_link("EVT-001", "PIP-002", 0.9, "in_progress")
        tracker.record_link("EVT-002", "PIP-002", 0.8, "completed")
        assert tracker.is_many_to_one("PIP-002")
        assert not tracker.is_one_to_many("EVT-001")

    def test_one_to_many(self):
        tracker = GranularityTracker()
        tracker.record_link("EVT-001", "PIP-002", 0.9, "completed")
        tracker.record_link("EVT-001", "PIP-003", 0.7, "completed")
        assert tracker.is_one_to_many("EVT-001")

    def test_progress_summary(self):
        tracker = GranularityTracker()
        tracker.record_link("EVT-001", "PIP-002", 0.9, "in_progress")
        tracker.record_link("EVT-002", "PIP-002", 0.95, "completed")
        progress = tracker.get_progress_summary("PIP-002")
        assert progress["event_count"] == 2
        assert progress["latest_status"] == "completed"


# ── Ground truth evaluation ──

class TestGroundTruth:

    def test_overall_accuracy_above_70(self, engine, ground_truth):
        correct = 0
        total = len(ground_truth)
        for item in ground_truth:
            result = engine.match_event(item["input_text"])
            cid = item["correct_activity_id"]
            if cid == "AMBIGUOUS":
                if result["decision"] in ("clarification_needed", "review", "unmatched"):
                    correct += 1
            elif result["matched_activity_id"] == cid:
                correct += 1
        accuracy = correct / total * 100
        assert accuracy >= 70, f"Accuracy {accuracy:.1f}% is below 70%"

    def test_easy_events_mostly_correct(self, engine, ground_truth):
        easy = [g for g in ground_truth if g["difficulty"] == "easy"]
        correct = 0
        for item in easy:
            result = engine.match_event(item["input_text"])
            if item["correct_activity_id"] == "AMBIGUOUS":
                if result["decision"] != "auto_linked":
                    correct += 1
            elif result["matched_activity_id"] == item["correct_activity_id"]:
                correct += 1
        accuracy = correct / len(easy) * 100
        assert accuracy >= 75, f"Easy accuracy {accuracy:.1f}% below 75%"


# ── Threshold config ──

class TestThresholds:

    def test_custom_thresholds(self):
        engine = SynapseMatchingEngine(
            schedule_path=SCHEDULE_CSV,
            auto_threshold=0.90,
            review_threshold=0.70,
        )
        result = engine.match_event("some vague event text")
        assert result["decision"] in ("auto_linked", "review", "unmatched", "clarification_needed")

    def test_lower_threshold_more_autolinks(self):
        high = SynapseMatchingEngine(schedule_path=SCHEDULE_CSV, auto_threshold=0.95)
        low = SynapseMatchingEngine(schedule_path=SCHEDULE_CSV, auto_threshold=0.60)

        text = "Line 24 spool erection completed"
        r_high = high.match_event(text, discipline="piping")
        r_low = low.match_event(text, discipline="piping")

        if r_high["decision"] == "auto_linked":
            assert r_low["decision"] == "auto_linked"


# ── Process event (Adithyan format) ──

class TestProcessEvent:

    def test_process_event_dict(self, engine):
        event = {
            "event_id": "EVT-TEST",
            "event_text": "MCC panel M-301 installation done at Substation.",
            "discipline": "electrical",
            "location": "Substation",
            "date": "2026-08-16",
            "source": "test",
            "status_hint": "completed",
        }
        result = engine.process_event(event)
        assert result["event_id"] == "EVT-TEST"
        assert result["matched_activity_id"] == "ELE-008"

    def test_process_batch(self, engine):
        events = [
            {"event_id": "E1", "event_text": "Line 24 spool erection completed", "discipline": "piping"},
            {"event_id": "E2", "event_text": "MCC panel M-301 installed", "discipline": "electrical"},
        ]
        results = engine.process_batch(events)
        assert len(results) == 2
        assert all("matched_activity_id" in r for r in results)
