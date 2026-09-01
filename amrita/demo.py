"""
SYNAPSE — Live Demo Script
Shows the full pipeline running end-to-end.

Run from the src/ folder:
    python demo.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from matcher import SynapseMatchingEngine


def print_result(result):
    print(f"  Decision   : {result['decision'].upper()}")
    if result["matched_activity_id"]:
        print(f"  Matched to : {result['matched_activity_id']} — {result['matched_activity_name']}")
    print(f"  Confidence : {result['confidence']}")
    if result["requires_clarification"]:
        print(f"  *** AGENTIC QUESTION ***")
        print(f"  {result['clarification_question']}")
    print(f"  Top candidates:")
    for c in result["candidates"]:
        print(f"    {c['activity_id']}  {c['name']}  [{c['score']}]")


def main():
    sep = "=" * 65

    # ---- Load engine ----
    schedule_path = os.path.join(os.path.dirname(__file__), "../data/schedule.csv")
    engine = SynapseMatchingEngine(schedule_path=schedule_path)

    print(f"\n{sep}")
    print("  SYNAPSE DEMO — MATCHING FIELD EVENTS TO SCHEDULE")
    print(sep)

    # ----------------------------------------------------------------
    # DEMO 1: Easy match — clear identifier, single correct answer
    # ----------------------------------------------------------------
    print("\n[DEMO 1] Easy match with clear identifier")
    print("-" * 65)
    text = "Line 24 spool erection was completed by the piping crew today at Unit 4."
    print(f"  Input: {text}")
    result = engine.match_event(text, discipline="piping", location="Unit 4")
    print_result(result)

    # ----------------------------------------------------------------
    # DEMO 2: Medium match — paraphrase, no direct keyword
    # ----------------------------------------------------------------
    print("\n[DEMO 2] Paraphrase — 'hydrotesting' vs 'hydrotest'")
    print("-" * 65)
    text = "Hydrotesting for line 24 completed successfully. No leaks observed."
    print(f"  Input: {text}")
    result = engine.match_event(text, discipline="piping")
    print_result(result)

    # ----------------------------------------------------------------
    # DEMO 3: Hard match — cross-discipline trap
    # ----------------------------------------------------------------
    print("\n[DEMO 3] Cross-discipline trap — CV-201 is instrumentation not piping")
    print("-" * 65)
    text = "Control valve CV-201 installation on Line 25 completed today."
    print(f"  Input: {text}")
    result = engine.match_event(text)
    print_result(result)

    # ----------------------------------------------------------------
    # DEMO 4: Agentic clarification — too vague to match
    # ----------------------------------------------------------------
    print("\n[DEMO 4] Agentic clarification — 'Erection completed today' is too vague")
    print("-" * 65)
    text = "Erection completed today."
    print(f"  Input: {text}")
    result = engine.match_event(text)
    print_result(result)

    # ----------------------------------------------------------------
    # DEMO 5: Another ambiguous — 'welding done' with multiple welding activities
    # ----------------------------------------------------------------
    print("\n[DEMO 5] Agentic clarification — 'welding done' — which line?")
    print("-" * 65)
    text = "welding done"
    print(f"  Input: {text}")
    result = engine.match_event(text)
    print_result(result)

    # ----------------------------------------------------------------
    # DEMO 6: Active learning feedback
    # ----------------------------------------------------------------
    print(f"\n{sep}")
    print("  ACTIVE LEARNING — recording reviewer feedback")
    print(sep)

    engine.record_feedback(
        event_id="EVT-001",
        event_text="Line 24 spool erection was completed by the piping crew today at Unit 4.",
        correct_activity_id="PIP-002",
        approved=True
    )

    engine.record_feedback(
        event_id="EVT-999",
        event_text="Pipe work in unit 4",
        correct_activity_id="PIP-001",
        approved=False
    )

    engine.save_feedback(
        path=os.path.join(os.path.dirname(__file__), "../data/feedback_store.json")
    )

    # ----------------------------------------------------------------
    # DEMO 7: Adithyan's format — full ExecutionEvent dict
    # ----------------------------------------------------------------
    print(f"\n{sep}")
    print("  PROCESSING ADITHYAN'S ExecutionEvent FORMAT")
    print(sep)

    execution_events = [
        {
            "event_id": "EVT-A01",
            "event_text": "MCC panel M-301 installation done at Substation.",
            "discipline": "electrical",
            "location": "Substation",
            "date": "2026-08-29",
            "source": "DPR_2026_08_29",
            "status_hint": "completed"
        },
        {
            "event_id": "EVT-A02",
            "event_text": "Pump P-101 alignment completed and signed off by vendor rep.",
            "discipline": "mechanical",
            "location": "Unit 4",
            "date": "2026-08-29",
            "source": "DPR_2026_08_29",
            "status_hint": "completed"
        },
        {
            "event_id": "EVT-A03",
            "event_text": "Pipe work done in Unit 4.",
            "discipline": "piping",
            "location": "Unit 4",
            "date": "2026-08-30",
            "source": "supervisor_message",
            "status_hint": "unknown"
        },
    ]

    results = engine.process_batch(execution_events)

    for r in results:
        print(f"\n  Event: {r['event_id']}  |  {r['original_text']}")
        print_result(r)

    print(f"\n{sep}")
    print("  Demo complete.")
    print(sep + "\n")


if __name__ == "__main__":
    main()
