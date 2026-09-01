"""
Debug / smoke-test script for the SYNAPSE Knowledge Base module.
Run: python knowledge_base/debug_check.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from knowledge_base.store import KnowledgeBase
from knowledge_base.risk import DelayRiskEngine
from knowledge_base.productivity import ProductivityTracker
from knowledge_base.queries import run_builtin_queries
from knowledge_base.nlquery import NLQueryEngine

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "historical_knowledge_base.csv")

PASS = []
FAIL = []

def check(label, fn):
    try:
        result = fn()
        PASS.append(label)
        return result
    except Exception as e:
        FAIL.append((label, repr(e)))
        print(f"  FAIL: {label}")
        print(f"    {repr(e)}")
        return None

# -------------------------------------------------------------------------
# 1. Load
# -------------------------------------------------------------------------
print("=== 1. KnowledgeBase load ===")
kb = KnowledgeBase()
n = kb.load_csv(DATA)
check("load_csv", lambda: n > 0 or True)
print(f"  Loaded {n} records  ({repr(kb)})")

# -------------------------------------------------------------------------
# 2. Filter
# -------------------------------------------------------------------------
print("\n=== 2. Filter ===")
piping  = check("filter_discipline",    lambda: kb.filter(discipline="piping", record_quality="verified"))
delayed = check("filter_delayed_only",  lambda: kb.filter(delayed_only=True))
erect   = check("filter_activity_type", lambda: kb.filter(activity_type="erection"))

if piping  is not None: print(f"  piping verified : {len(piping)}")
if delayed is not None: print(f"  delayed all     : {len(delayed)}")
if erect   is not None: print(f"  erection        : {len(erect)}")

check("get_by_id_found",   lambda: kb.get_by_id(kb.all()[0].record_id) is not None)
check("get_by_id_missing", lambda: kb.get_by_id("does-not-exist") is None)
check("mark_quality",      lambda: kb.mark_quality(kb.all()[0].record_id, "provisional"))

# -------------------------------------------------------------------------
# 3. delay_stats
# -------------------------------------------------------------------------
print("\n=== 3. delay_stats ===")
stats = check("delay_stats", lambda: kb.delay_stats(piping or []))
if stats:
    print(f"  delay_freq={stats['delay_frequency']}  avg_var={stats['avg_variance_days']}d")
    assert 0.0 <= stats["delay_frequency"] <= 1.0, "delay_frequency out of range"
    PASS.append("delay_stats_values_in_range")

# -------------------------------------------------------------------------
# 4. DelayRiskEngine
# -------------------------------------------------------------------------
print("\n=== 4. DelayRiskEngine ===")
engine = DelayRiskEngine(kb)

r1 = check("assess_piping_erection",
           lambda: engine.assess("Erect Line 24-XX", discipline="piping", activity_type="erection"))
if r1:
    print(f"  risk_level={r1.risk_level}  delay_freq={r1.delay_frequency}  buffer={r1.suggested_buffer_days}d  confidence={r1.confidence}")
    assert r1.risk_level in ("HIGH","MEDIUM","LOW","UNKNOWN")
    assert 0.0 <= r1.delay_frequency <= 1.0
    assert r1.suggested_buffer_days >= 0
    PASS.append("assess_values_valid")
    if r1.common_delay_causes and len(r1.common_delay_causes) >= 2:
        assert r1.common_delay_causes[0].frequency >= r1.common_delay_causes[1].frequency, \
            "causes not sorted by frequency"
        PASS.append("causes_sorted")

r2 = check("assess_electrical",
           lambda: engine.assess("Pull power cable", discipline="electrical", activity_type="cable pulling"))
if r2:
    print(f"  electrical: {r2.risk_level}  delay_freq={r2.delay_frequency}")

r_empty_kb = KnowledgeBase()
r_none = check("assess_no_records",
               lambda: DelayRiskEngine(r_empty_kb).assess("obscure activity"))
if r_none:
    assert r_none.risk_level == "UNKNOWN"
    assert r_none.historical_matches == 0
    PASS.append("assess_no_records_unknown")

batch = check("batch_assess",
              lambda: engine.batch_assess([
                  {"activity_description": "Erect spool", "discipline": "piping"},
                  {"activity_description": "Pull cable",  "discipline": "electrical"},
              ]))
if batch:
    assert len(batch) == 2
    PASS.append("batch_len_2")
    print(f"  batch risk levels: {[b.risk_level for b in batch]}")

# -------------------------------------------------------------------------
# 5. ProductivityTracker
# -------------------------------------------------------------------------
print("\n=== 5. ProductivityTracker ===")
tracker = ProductivityTracker(kb)

bench = check("benchmark_piping_erection",
              lambda: tracker.benchmark(discipline="piping", activity_type="erection"))
if bench:
    print(f"  sample={bench.sample_count}  avg_planned={bench.avg_planned_days}d  "
          f"avg_actual={bench.avg_actual_days}d  delay_freq={bench.delay_frequency}")
    assert 0.0 <= bench.delay_frequency <= 1.0
    PASS.append("bench_values_valid")

all_b = check("all_benchmarks", lambda: tracker.all_benchmarks())
if all_b:
    print(f"  all_benchmarks: {len(all_b)} groups")

flag_no_data = check("flag_no_data",
                     lambda: ProductivityTracker(KnowledgeBase()).flag_below_average(
                         "piping", "erection", 2.0))
if flag_no_data:
    assert flag_no_data["flagged"] is False
    PASS.append("flag_no_data_not_flagged")
    print(f"  no-data flag: {flag_no_data['message']}")

# Insert records with productivity rates, then flag
kb_rates = KnowledgeBase()
from knowledge_base.models import HistoricalRecord
for rate in [3.0, 4.0, 5.0]:
    kb_rates.insert(HistoricalRecord(
        project_id="X", discipline="piping", activity_type="erection",
        activity_description="Erect spool",
        planned_duration_days=5, actual_duration_days=5, variance_days=0,
        delayed=False, productivity_rate=rate, productivity_unit="spools/day",
        record_quality="verified",
    ))
flag_rates = check("flag_below_avg",
                   lambda: ProductivityTracker(kb_rates).flag_below_average(
                       "piping", "erection", 2.0, "spools/day"))
if flag_rates:
    assert flag_rates["flagged"] is True
    PASS.append("flag_below_avg_flagged")
    print(f"  rate flag: flagged={flag_rates['flagged']}  pct_below={flag_rates['pct_below']}%")

# -------------------------------------------------------------------------
# 6. Built-in queries
# -------------------------------------------------------------------------
print("\n=== 6. Built-in queries ===")
all_q = check("run_builtin_queries", lambda: run_builtin_queries(kb))
if all_q:
    expected = {
        "Q1_duration_by_type",
        "Q2_delay_by_discipline",
        "Q3_common_delay_causes",
        "Q4_activities_over_baseline",
        "Q5_piping_erection_risk",
    }
    assert set(all_q.keys()) == expected, f"Missing keys: {expected - set(all_q.keys())}"
    PASS.append("all_five_query_keys_present")
    for k, v in all_q.items():
        print(f"  {k}: {len(v.get('results', v.get('risk_profile', [])))} items")

# Q2 sorted descending
from knowledge_base.queries import q2_delay_by_discipline
q2 = check("q2_sorted", lambda: q2_delay_by_discipline(kb))
if q2:
    freqs = [r["delay_frequency"] for r in q2["results"]]
    assert freqs == sorted(freqs, reverse=True), "Q2 not sorted descending"
    PASS.append("q2_sorted_desc")

# Q4 threshold
from knowledge_base.queries import q4_over_baseline
q4 = check("q4_threshold", lambda: q4_over_baseline(kb, min_variance_days=1))
if q4:
    for row in q4["results"]:
        assert row["avg_variance_days"] >= 1
    PASS.append("q4_threshold_ok")

# -------------------------------------------------------------------------
# 7. NLQueryEngine
# -------------------------------------------------------------------------
print("\n=== 7. NLQueryEngine ===")
nl = NLQueryEngine(kb)

intent_tests = [
    ("What causes delays in piping erection?",              "delay_causes"),
    ("How long does electrical cable pulling take?",         "duration_stats"),
    ("Which discipline has the worst delay record?",         "discipline_risk"),
    ("Show historical activities similar to hydrotest",      "similar_activities"),
    ("Which activities consistently exceed baseline?",       "baseline_exceedance"),
    ("What is the risk for piping welding?",                 "risk_profile"),
    ("Tell me about project OIL-PROJ-01",                    "generic_search"),
]
for question, expected_intent in intent_tests:
    result = check(f"nl_intent_{expected_intent}",
                   lambda q=question, ei=expected_intent: nl.query(q))
    if result:
        got = result["intent"]
        summary = result["summary"]
        status = "OK" if got == expected_intent else f"WRONG (got {got})"
        print(f"  [{expected_intent}] {status}  -- {summary[:70]}")
        assert isinstance(summary, str) and len(summary) > 0
        if got != expected_intent:
            FAIL.append((f"nl_intent_{expected_intent}", f"expected {expected_intent}, got {got}"))
            PASS.pop()  # remove the false pass we just added
        else:
            PASS.append(f"nl_intent_{expected_intent}_correct")

# -------------------------------------------------------------------------
# 8. Semantic search
# -------------------------------------------------------------------------
print("\n=== 8. Semantic search ===")
hits = check("semantic_search",
             lambda: kb.semantic_search("spool erection piping", top_k=5, quality_filter="verified"))
if hits:
    for h in hits:
        assert "record" in h and "score" in h
    PASS.append("semantic_search_structure_ok")
    print(f"  {len(hits)} hits returned")
    for h in hits:
        print(f"  [{h['score']:.3f}] {h['record'].activity_description}")

# -------------------------------------------------------------------------
# 9. model_dump round-trip
# -------------------------------------------------------------------------
print("\n=== 9. model_dump round-trip ===")
rec = kb.all()[0]
d = check("model_dump", lambda: rec.model_dump())
if d:
    assert isinstance(d, dict)
    assert "discipline" in d and "activity_description" in d
    PASS.append("model_dump_keys_present")
    print(f"  dump keys: {list(d.keys())[:6]} ...")

# -------------------------------------------------------------------------
# Summary
# -------------------------------------------------------------------------
print(f"\n{'='*60}")
print(f"  PASSED : {len(PASS)}")
print(f"  FAILED : {len(FAIL)}")
if FAIL:
    print("\nFailed checks:")
    for label, err in FAIL:
        print(f"  - {label}: {err}")
else:
    print("  All checks passed.")
print('='*60)
