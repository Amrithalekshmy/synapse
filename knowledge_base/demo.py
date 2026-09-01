"""
SYNAPSE Knowledge Base — Demo Script
Adithyagopan's module.

Demonstrates the complete demo flow from 04_ADITHYAGOPAN_KNOWLEDGE_BASE.md:

  Project closes
        |
  Verified execution history saved
        |
  User asks: "What usually delays piping erection?"
        |
  Relevant historical records
        |
  AI summary + supporting records

Run from the synapse root:
    python -m knowledge_base.demo
"""

from __future__ import annotations

import json
import os
import sys

_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from knowledge_base.store import KnowledgeBase
from knowledge_base.risk import DelayRiskEngine
from knowledge_base.productivity import ProductivityTracker
from knowledge_base.queries import run_builtin_queries
from knowledge_base.nlquery import NLQueryEngine

DATA_CSV = os.path.join(_ROOT, "data", "historical_knowledge_base.csv")
SEP = "=" * 70


def section(title: str):
    print(f"\n{SEP}\n  {title}\n{SEP}")


def pp(obj):
    print(json.dumps(obj, indent=2, default=str))


def main():
    # -----------------------------------------------------------------------
    # 1. Load verified historical records
    # -----------------------------------------------------------------------
    section("1. LOAD HISTORICAL KNOWLEDGE BASE")
    kb = KnowledgeBase()
    n = kb.load_csv(DATA_CSV)
    print(f"Loaded {n} records from {DATA_CSV}")
    print(repr(kb))

    # -----------------------------------------------------------------------
    # 2. Minimum version — filter queries
    # -----------------------------------------------------------------------
    section("2. FILTER QUERIES (minimum version)")

    piping = kb.filter(discipline="piping", record_quality="verified")
    print(f"Verified piping records   : {len(piping)}")

    delayed = kb.filter(discipline="piping", delayed_only=True, record_quality="verified")
    print(f"Delayed piping records    : {len(delayed)}")

    erection = kb.filter(activity_type="erection", record_quality="verified")
    print(f"Erection records          : {len(erection)}")

    # -----------------------------------------------------------------------
    # 3. Minimum version — 5 built-in queries
    # -----------------------------------------------------------------------
    section("3. FIVE BUILT-IN HISTORICAL QUERIES (minimum version)")
    for name, data in run_builtin_queries(kb).items():
        print(f"\n--- {name} ---")
        pp(data)

    # -----------------------------------------------------------------------
    # 4. Delay Risk Intelligence (feeds Adithyanbalu)
    # -----------------------------------------------------------------------
    section("4. DELAY RISK INTELLIGENCE (feeds Adithyanbalu's risk engine)")

    engine = DelayRiskEngine(kb)

    # Primary demo from spec: Erect Line 24-XX
    risk = engine.assess(
        activity_description="Erect Line 24-XX spool",
        discipline="piping",
        activity_type="erection",
        planned_duration_days=5,
    )
    print("\nActivity : 'Erect Line 24-XX spool'")
    pp(risk.model_dump() if hasattr(risk, "model_dump") else risk.dict())

    risk2 = engine.assess(
        activity_description="Pull power cable in Area B",
        discipline="electrical",
        activity_type="cable pulling",
        planned_duration_days=5,
    )
    print("\nActivity : 'Pull power cable in Area B'")
    pp(risk2.model_dump() if hasattr(risk2, "model_dump") else risk2.dict())

    # -----------------------------------------------------------------------
    # 5. Productivity benchmarking
    # -----------------------------------------------------------------------
    section("5. PRODUCTIVITY BENCHMARKING")

    tracker = ProductivityTracker(kb)
    bench = tracker.benchmark(discipline="piping", activity_type="erection")
    print("\nPiping erection benchmark:")
    pp(bench.model_dump() if hasattr(bench, "model_dump") else bench.dict())

    flag = tracker.flag_below_average(
        discipline="piping",
        activity_type="erection",
        current_rate=2.1,
        productivity_unit="spools/day",
    )
    print("\nRate flag (current = 2.1 spools/day):")
    pp(flag)

    # -----------------------------------------------------------------------
    # 6. Natural-language query layer (strong version)
    # -----------------------------------------------------------------------
    section("6. NATURAL-LANGUAGE QUERIES (strong version)")

    nl = NLQueryEngine(kb)
    questions = [
        "What usually delays piping erection?",
        "How long does electrical cable pulling typically take?",
        "Which discipline has the worst delay record?",
        "Show historical activities similar to hydrotest",
        "Which activities consistently exceed their baseline duration?",
        "What is the risk for piping welding?",
    ]
    for q in questions:
        result = nl.query(q)
        print(f"\nQ: {q}")
        print(f"=> {result['summary']}")

    # -----------------------------------------------------------------------
    # 7. Semantic similarity search (strong version)
    # -----------------------------------------------------------------------
    section("7. SEMANTIC SIMILARITY SEARCH (strong version)")
    hits = kb.semantic_search("spool erection line piping", top_k=5, quality_filter="verified")
    print("\nTop 5 similar historical records:")
    for h in hits:
        r = h["record"]
        print(
            f"  [{h['score']:.3f}] {r.activity_description} | "
            f"{r.discipline} | var={r.variance_days}d | cause={r.delay_cause or '-'}"
        )

    # -----------------------------------------------------------------------
    # Done
    # -----------------------------------------------------------------------
    section("DEMO COMPLETE")
    print(
        "Knowledge Base is operational.\n"
        "Delay risk intelligence ready for Adithyanbalu's risk engine.\n"
        "FastAPI endpoints: knowledge_base.api.router\n"
        "PostgreSQL schema: knowledge_base.schema\n"
    )


if __name__ == "__main__":
    main()
