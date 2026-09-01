"""
Tests for the SYNAPSE Knowledge Base module.
Adithyagopan's module.

Run from the synapse root:
    pytest tests/test_knowledge_base.py -v
"""

from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)

from knowledge_base.models import HistoricalRecord, RecordQuality
from knowledge_base.store import KnowledgeBase
from knowledge_base.risk import DelayRiskEngine
from knowledge_base.productivity import ProductivityTracker
from knowledge_base.queries import (
    q1_duration_by_type,
    q2_delay_by_discipline,
    q3_common_causes,
    q4_over_baseline,
    q5_risk_profile,
    run_builtin_queries,
)
from knowledge_base.nlquery import NLQueryEngine

DATA_CSV = os.path.join(_ROOT, "data", "historical_knowledge_base.csv")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def empty_kb():
    return KnowledgeBase()


@pytest.fixture()
def sample_record():
    return HistoricalRecord(
        project_id="OIL-TEST-01",
        activity_id="PIP-T-001",
        activity_description="Erect test spool",
        discipline="piping",
        activity_type="erection",
        location_type="unit",
        planned_duration_days=5,
        actual_duration_days=7,
        variance_days=2,
        delayed=True,
        delay_cause="crane availability",
        record_quality="verified",
    )


@pytest.fixture()
def loaded_kb():
    kb = KnowledgeBase()
    if os.path.exists(DATA_CSV):
        kb.load_csv(DATA_CSV)
    else:
        _add_synthetic(kb)
    return kb


def _add_synthetic(kb: KnowledgeBase):
    """Minimal synthetic records for offline runs."""
    for i in range(5):
        kb.insert(HistoricalRecord(
            project_id="SYN-01",
            discipline="piping",
            activity_type="erection",
            activity_description="Erect pipe spool",
            location_type="unit",
            planned_duration_days=5,
            actual_duration_days=7,
            variance_days=2,
            delayed=True,
            delay_cause="crane availability",
            record_quality="verified",
        ))
    kb.insert(HistoricalRecord(
        project_id="SYN-01",
        discipline="electrical",
        activity_type="cable pulling",
        activity_description="Pull power cable",
        location_type="area",
        planned_duration_days=5,
        actual_duration_days=6,
        variance_days=1,
        delayed=True,
        delay_cause="cable drum issue",
        record_quality="verified",
    ))
    kb.insert(HistoricalRecord(
        project_id="SYN-01",
        discipline="civil",
        activity_type="excavation",
        activity_description="Excavation for foundation",
        location_type="unit",
        planned_duration_days=4,
        actual_duration_days=4,
        variance_days=0,
        delayed=False,
        record_quality="verified",
    ))


# ---------------------------------------------------------------------------
# KnowledgeBase store
# ---------------------------------------------------------------------------

class TestStore:

    def test_insert_returns_id(self, empty_kb, sample_record):
        rid = empty_kb.insert(sample_record)
        assert rid
        assert len(empty_kb) == 1

    def test_bulk_insert(self, empty_kb, sample_record):
        r2 = HistoricalRecord(project_id="X", activity_description="Another")
        n = empty_kb.bulk_insert([sample_record, r2])
        assert n == 2
        assert len(empty_kb) == 2

    def test_get_by_id(self, empty_kb, sample_record):
        rid = empty_kb.insert(sample_record)
        found = empty_kb.get_by_id(rid)
        assert found is not None
        assert found.activity_description == "Erect test spool"

    def test_get_by_id_missing(self, empty_kb):
        assert empty_kb.get_by_id("bad-id") is None

    def test_filter_discipline(self, loaded_kb):
        piping = loaded_kb.filter(discipline="piping")
        assert all(r.discipline == "piping" for r in piping)
        assert len(piping) > 0

    def test_filter_quality(self, loaded_kb):
        verified = loaded_kb.filter(record_quality="verified")
        assert all(r.record_quality == "verified" for r in verified)

    def test_filter_delayed_only(self, loaded_kb):
        delayed = loaded_kb.filter(delayed_only=True)
        assert all(r.delayed for r in delayed)

    def test_filter_activity_type(self, loaded_kb):
        erection = loaded_kb.filter(activity_type="erection")
        assert all(r.activity_type == "erection" for r in erection)

    def test_mark_quality(self, empty_kb, sample_record):
        rid = empty_kb.insert(sample_record)
        ok = empty_kb.mark_quality(rid, "rejected")
        assert ok
        assert empty_kb.get_by_id(rid).record_quality == "rejected"

    def test_load_csv(self, empty_kb):
        if not os.path.exists(DATA_CSV):
            pytest.skip("CSV not found")
        n = empty_kb.load_csv(DATA_CSV)
        assert n > 0
        assert len(empty_kb) == n

    def test_delay_stats(self, loaded_kb):
        records = loaded_kb.filter(discipline="piping", record_quality="verified")
        stats = loaded_kb.delay_stats(records)
        assert "delay_frequency" in stats
        assert 0.0 <= stats["delay_frequency"] <= 1.0

    def test_semantic_search_no_crash(self, loaded_kb):
        hits = loaded_kb.semantic_search("spool erection piping", top_k=3)
        assert isinstance(hits, list)
        for h in hits:
            assert "record" in h
            assert "score" in h


# ---------------------------------------------------------------------------
# DelayRiskEngine
# ---------------------------------------------------------------------------

class TestRisk:

    def test_basic_assess(self, loaded_kb):
        engine = DelayRiskEngine(loaded_kb)
        result = engine.assess("Erect Line 24-XX", discipline="piping", activity_type="erection")
        assert result.historical_matches >= 0
        assert result.risk_level in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
        assert 0.0 <= result.delay_frequency <= 1.0

    def test_no_records_gives_unknown(self, empty_kb):
        engine = DelayRiskEngine(empty_kb)
        result = engine.assess("obscure activity")
        assert result.risk_level == "UNKNOWN"
        assert result.historical_matches == 0

    def test_buffer_non_negative(self, loaded_kb):
        engine = DelayRiskEngine(loaded_kb)
        result = engine.assess("Erect spool", discipline="piping")
        assert result.suggested_buffer_days >= 0

    def test_causes_ranked_descending(self, loaded_kb):
        engine = DelayRiskEngine(loaded_kb)
        result = engine.assess("erection", discipline="piping", activity_type="erection")
        causes = result.common_delay_causes
        if len(causes) >= 2:
            assert causes[0].frequency >= causes[1].frequency

    def test_all_delayed_gives_high(self, empty_kb):
        for _ in range(10):
            empty_kb.insert(HistoricalRecord(
                project_id="X", discipline="piping", activity_type="erection",
                activity_description="Erect spool",
                planned_duration_days=5, actual_duration_days=8, variance_days=3,
                delayed=True, delay_cause="crane availability", record_quality="verified",
            ))
        engine = DelayRiskEngine(empty_kb)
        result = engine.assess("erection", discipline="piping", activity_type="erection")
        assert result.risk_level == "HIGH"
        assert result.delay_frequency == 1.0

    def test_batch_assess(self, loaded_kb):
        engine = DelayRiskEngine(loaded_kb)
        results = engine.batch_assess([
            {"activity_description": "Erect spool", "discipline": "piping"},
            {"activity_description": "Pull cable",  "discipline": "electrical"},
        ])
        assert len(results) == 2


# ---------------------------------------------------------------------------
# ProductivityTracker
# ---------------------------------------------------------------------------

class TestProductivity:

    def test_benchmark_returns_object(self, loaded_kb):
        bench = ProductivityTracker(loaded_kb).benchmark(
            discipline="piping", activity_type="erection"
        )
        assert bench.discipline == "piping"
        assert bench.sample_count >= 0

    def test_delay_frequency_in_range(self, loaded_kb):
        bench = ProductivityTracker(loaded_kb).benchmark(discipline="piping")
        assert 0.0 <= bench.delay_frequency <= 1.0

    def test_flag_no_data(self, empty_kb):
        result = ProductivityTracker(empty_kb).flag_below_average("piping", "erection", 2.0)
        assert result["flagged"] is False
        assert "No historical" in result["message"]

    def test_flag_with_rates(self, empty_kb):
        for rate in [3.0, 4.0, 5.0]:
            empty_kb.insert(HistoricalRecord(
                project_id="X", discipline="piping", activity_type="erection",
                activity_description="Erect spool",
                planned_duration_days=5, actual_duration_days=5, variance_days=0,
                delayed=False, productivity_rate=rate, productivity_unit="spools/day",
                record_quality="verified",
            ))
        result = ProductivityTracker(empty_kb).flag_below_average(
            "piping", "erection", 2.0, "spools/day"
        )
        assert result["flagged"] is True


# ---------------------------------------------------------------------------
# Built-in queries
# ---------------------------------------------------------------------------

class TestQueries:

    def test_q1(self, loaded_kb):
        r = q1_duration_by_type(loaded_kb, discipline="piping")
        assert "results" in r
        assert isinstance(r["results"], list)

    def test_q2_sorted(self, loaded_kb):
        r = q2_delay_by_discipline(loaded_kb)
        freqs = [x["delay_frequency"] for x in r["results"]]
        assert freqs == sorted(freqs, reverse=True)

    def test_q3_causes(self, loaded_kb):
        r = q3_common_causes(loaded_kb, discipline="piping")
        assert "results" in r

    def test_q4_threshold(self, loaded_kb):
        r = q4_over_baseline(loaded_kb, min_variance_days=1)
        for item in r["results"]:
            assert item["avg_variance_days"] >= 1

    def test_q5_risk(self, loaded_kb):
        r = q5_risk_profile(loaded_kb, activity_type="erection", discipline="piping")
        assert "risk_profile" in r

    def test_run_all(self, loaded_kb):
        all_q = run_builtin_queries(loaded_kb)
        assert set(all_q.keys()) == {
            "Q1_duration_by_type",
            "Q2_delay_by_discipline",
            "Q3_common_delay_causes",
            "Q4_activities_over_baseline",
            "Q5_piping_erection_risk",
        }


# ---------------------------------------------------------------------------
# NLQueryEngine
# ---------------------------------------------------------------------------

class TestNL:

    def test_delay_causes_intent(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("What causes delays in piping erection?")
        assert r["intent"] == "delay_causes"
        assert r["summary"]

    def test_duration_intent(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("How long does electrical cable pulling take?")
        assert r["intent"] == "duration_stats"

    def test_discipline_risk_intent(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("Which discipline has the worst delay record?")
        assert r["intent"] == "discipline_risk"

    def test_similar_intent(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("Show historical activities similar to hydrotest")
        assert r["intent"] == "similar_activities"

    def test_baseline_intent(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("Which activities consistently exceed baseline?")
        assert r["intent"] == "baseline_exceedance"

    def test_risk_intent(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("What is the risk for piping welding?")
        assert r["intent"] == "risk_profile"

    def test_generic_fallback(self, loaded_kb):
        r = NLQueryEngine(loaded_kb).query("Tell me about project OIL-PROJ-01")
        assert r["intent"] == "generic_search"

    def test_summary_always_str(self, loaded_kb):
        nl = NLQueryEngine(loaded_kb)
        for q in ["What causes delays?", "How long does welding take?", "Show similar activities"]:
            assert isinstance(nl.query(q)["summary"], str)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:

    def test_quality_enum(self):
        assert RecordQuality.VERIFIED   == "verified"
        assert RecordQuality.PROVISIONAL == "provisional"
        assert RecordQuality.REJECTED   == "rejected"

    def test_record_defaults(self):
        r = HistoricalRecord(project_id="X", activity_description="Test")
        assert r.record_quality == "provisional"
        assert r.delayed is False
        assert r.variance_days == 0

    def test_model_dump(self, sample_record):
        d = sample_record.model_dump()
        assert isinstance(d, dict)
        assert d["discipline"] == "piping"
        assert d["delayed"] is True
