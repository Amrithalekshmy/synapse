"""
SYNAPSE — Evaluation Script
Runs the matching engine against ground_truth.json and prints accuracy.

Run this from the src/ folder:
    python evaluate.py
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from matcher import SynapseMatchingEngine


def evaluate():
    # Load engine with synthetic schedule (Yazeen's output stand-in)
    engine = SynapseMatchingEngine(
        schedule_path=os.path.join(os.path.dirname(__file__), "../data/schedule.csv")
    )

    # Load ground truth answer key
    gt_path = os.path.join(os.path.dirname(__file__), "../data/ground_truth.json")
    with open(gt_path) as f:
        ground_truth = json.load(f)

    # Counters
    correct = 0
    wrong = 0
    ambiguous_correct = 0
    total = len(ground_truth)
    details = []

    for item in ground_truth:
        event_text  = item["input_text"]
        correct_id  = item["correct_activity_id"]
        difficulty  = item["difficulty"]
        event_id    = item["event_id"]
        note        = item.get("note", "")

        # Run matcher — pass discipline/location if available in ground truth
        # In real usage Adithyan provides these; in eval we don't have them so
        # we test the engine without hints (harder, more honest evaluation)
        result = engine.match_event(event_text)

        predicted_id = result["matched_activity_id"]
        decision     = result["decision"]
        confidence   = result["confidence"]

        # Evaluate result
        if correct_id == "AMBIGUOUS":
            # These events should NOT be auto-linked
            if decision in ("clarification_needed", "review", "unmatched"):
                status = "CORRECT"
                ambiguous_correct += 1
            else:
                status = "WRONG  "
                wrong += 1

        elif predicted_id == correct_id:
            status = "CORRECT"
            correct += 1

        else:
            status = "WRONG  "
            wrong += 1

        details.append({
            "event_id":   event_id,
            "difficulty": difficulty,
            "input":      event_text,
            "expected":   correct_id,
            "predicted":  predicted_id,
            "confidence": confidence,
            "decision":   decision,
            "status":     status,
            "note":       note,
        })

    # ---- Print results ----
    sep = "=" * 65

    print(f"\n{sep}")
    print("  SYNAPSE MATCHING ENGINE — EVALUATION REPORT")
    print(sep)
    print(f"  Total events tested   : {total}")
    print(f"  Correct matches       : {correct}")
    print(f"  Ambiguous handled OK  : {ambiguous_correct}")
    print(f"  Wrong matches         : {wrong}")

    overall_acc = (correct + ambiguous_correct) / total * 100
    print(f"\n  Overall accuracy      : {overall_acc:.1f}%")

    # Accuracy by difficulty
    for diff in ("easy", "medium", "hard", "very_hard"):
        subset = [d for d in details if d["difficulty"] == diff]
        if not subset:
            continue
        diff_correct = sum(1 for d in subset if d["status"] == "CORRECT")
        print(f"  Accuracy [{diff:<9}] : {diff_correct}/{len(subset)}")

    print(f"\n{sep}")
    print("  DETAILED RESULTS")
    print(sep)

    for d in details:
        icon = "✓" if d["status"] == "CORRECT" else "✗"
        print(f"\n  {icon} {d['event_id']}  [{d['difficulty']}]  {d['decision'].upper()}")
        print(f"    Input     : {d['input']}")
        print(f"    Expected  : {d['expected']}")
        print(f"    Predicted : {d['predicted']}  (confidence: {d['confidence']})")
        if d["note"]:
            print(f"    Note      : {d['note']}")

    print(f"\n{sep}\n")

    return {
        "total": total,
        "correct": correct,
        "ambiguous_correct": ambiguous_correct,
        "wrong": wrong,
        "accuracy": overall_acc,
    }


if __name__ == "__main__":
    evaluate()
