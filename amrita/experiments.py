"""
SYNAPSE — Baseline Comparison & Threshold Experiments
Compares: exact → fuzzy → embedding → hybrid (seven-layer)
"""

import json
import os

from .baselines import ExactMatcher, FuzzyMatcher
from .matcher import SynapseMatchingEngine


def run_baseline_comparison(schedule_path: str, ground_truth_path: str) -> dict:
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    engine = SynapseMatchingEngine(schedule_path=schedule_path)
    exact = ExactMatcher()
    fuzzy = FuzzyMatcher()

    results = {
        "exact": {"correct": 0, "wrong": 0, "total": 0},
        "fuzzy": {"correct": 0, "wrong": 0, "total": 0},
        "embedding": {"correct": 0, "wrong": 0, "total": 0},
        "hybrid": {"correct": 0, "wrong": 0, "total": 0},
    }

    details = []

    for item in ground_truth:
        event_text = item["input_text"]
        correct_id = item["correct_activity_id"]
        is_ambiguous = correct_id == "AMBIGUOUS"

        # Exact baseline
        exact_results = exact.match(event_text, engine.activities, top_k=1)
        exact_pred = exact_results[0]["activity_id"] if exact_results else None
        if is_ambiguous:
            results["exact"]["correct"] += 1
        elif exact_pred == correct_id:
            results["exact"]["correct"] += 1
        else:
            results["exact"]["wrong"] += 1
        results["exact"]["total"] += 1

        # Fuzzy baseline
        fuzzy_results = fuzzy.match(event_text, engine.activities, top_k=1)
        fuzzy_pred = fuzzy_results[0]["activity_id"] if fuzzy_results else None
        if is_ambiguous:
            results["fuzzy"]["correct"] += 1
        elif fuzzy_pred == correct_id:
            results["fuzzy"]["correct"] += 1
        else:
            results["fuzzy"]["wrong"] += 1
        results["fuzzy"]["total"] += 1

        # Embedding only (no boosts)
        emb_result = engine.match_event(event_text)
        emb_pred = emb_result["matched_activity_id"]
        if is_ambiguous:
            if emb_result["decision"] in ("clarification_needed", "review", "unmatched"):
                results["embedding"]["correct"] += 1
            else:
                results["embedding"]["wrong"] += 1
        elif emb_pred == correct_id:
            results["embedding"]["correct"] += 1
        else:
            results["embedding"]["wrong"] += 1
        results["embedding"]["total"] += 1

        # Hybrid (seven-layer with discipline/location)
        discipline = None
        location = None
        hybrid_result = engine.match_event(event_text, discipline=discipline, location=location)
        hybrid_pred = hybrid_result["matched_activity_id"]
        hybrid_decision = hybrid_result["decision"]

        if is_ambiguous:
            if hybrid_decision in ("clarification_needed", "review", "unmatched"):
                results["hybrid"]["correct"] += 1
            else:
                results["hybrid"]["wrong"] += 1
        elif hybrid_pred == correct_id:
            results["hybrid"]["correct"] += 1
        else:
            results["hybrid"]["wrong"] += 1
        results["hybrid"]["total"] += 1

        details.append({
            "event_id": item["event_id"],
            "difficulty": item["difficulty"],
            "correct": correct_id,
            "exact": exact_pred,
            "fuzzy": fuzzy_pred,
            "embedding": emb_pred,
            "hybrid": hybrid_pred,
        })

    for method in results:
        total = results[method]["total"]
        if total > 0:
            results[method]["accuracy"] = round(results[method]["correct"] / total * 100, 1)

    return {"summary": results, "details": details}


def run_threshold_experiment(schedule_path: str, ground_truth_path: str) -> dict:
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    thresholds = [
        (0.90, 0.70),
        (0.85, 0.65),
        (0.80, 0.60),
        (0.75, 0.55),
        (0.70, 0.50),
    ]

    results = []

    for auto_t, review_t in thresholds:
        engine = SynapseMatchingEngine(schedule_path=schedule_path,
                                        auto_threshold=auto_t, review_threshold=review_t)

        auto_linked = 0
        false_auto_link = 0
        review = 0
        unmatched = 0
        correct_auto = 0

        for item in ground_truth:
            event_text = item["input_text"]
            correct_id = item["correct_activity_id"]
            is_ambiguous = correct_id == "AMBIGUOUS"

            result = engine.match_event(event_text)
            decision = result["decision"]
            pred = result["matched_activity_id"]

            if decision == "auto_linked":
                auto_linked += 1
                if is_ambiguous or pred != correct_id:
                    false_auto_link += 1
                else:
                    correct_auto += 1
            elif decision == "review" or decision == "clarification_needed":
                review += 1
            else:
                unmatched += 1

        total = len(ground_truth)
        results.append({
            "auto_threshold": auto_t,
            "review_threshold": review_t,
            "auto_linked": auto_linked,
            "correct_auto": correct_auto,
            "false_auto_link": false_auto_link,
            "false_auto_link_rate": round(false_auto_link / max(auto_linked, 1) * 100, 1),
            "review": review,
            "unmatched": unmatched,
            "total": total,
        })

    return {"threshold_experiments": results}


def run_error_analysis(schedule_path: str, ground_truth_path: str) -> dict:
    with open(ground_truth_path) as f:
        ground_truth = json.load(f)

    engine = SynapseMatchingEngine(schedule_path=schedule_path)

    categories = {
        "discipline_confusion": [],
        "identifier_miss": [],
        "paraphrase_failure": [],
        "ambiguity_not_detected": [],
        "wrong_line": [],
        "other": [],
    }

    for item in ground_truth:
        event_text = item["input_text"]
        correct_id = item["correct_activity_id"]
        is_ambiguous = correct_id == "AMBIGUOUS"

        result = engine.match_event(event_text)
        pred = result["matched_activity_id"]
        decision = result["decision"]

        if is_ambiguous:
            if decision == "auto_linked":
                categories["ambiguity_not_detected"].append({
                    "event_id": item["event_id"],
                    "input": event_text,
                    "predicted": pred,
                    "confidence": result["confidence"],
                })
            continue

        if pred == correct_id:
            continue

        correct_act = engine._activity_map.get(correct_id, {})
        predicted_act = engine._activity_map.get(pred, {}) if pred else {}

        if correct_act.get("discipline") != predicted_act.get("discipline"):
            categories["discipline_confusion"].append({
                "event_id": item["event_id"],
                "input": event_text,
                "expected_discipline": correct_act.get("discipline"),
                "predicted_discipline": predicted_act.get("discipline"),
            })
        elif "line" in event_text.lower() or re.search(r"[A-Z]+-\d+", event_text):
            categories["identifier_miss"].append({
                "event_id": item["event_id"],
                "input": event_text,
                "expected": correct_id,
                "predicted": pred,
            })
        else:
            categories["other"].append({
                "event_id": item["event_id"],
                "input": event_text,
                "expected": correct_id,
                "predicted": pred,
            })

    summary = {cat: len(items) for cat, items in categories.items()}
    return {"error_categories": summary, "details": categories}


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(__file__))
    schedule = os.path.join(base, "data", "schedule.csv")
    gt = os.path.join(base, "data", "ground_truth.json")

    print("=" * 65)
    print("  BASELINE COMPARISON")
    print("=" * 65)
    comparison = run_baseline_comparison(schedule, gt)
    for method, stats in comparison["summary"].items():
        print(f"  {method:<12} accuracy: {stats.get('accuracy', 0):.1f}%  ({stats['correct']}/{stats['total']})")

    print("\n" + "=" * 65)
    print("  THRESHOLD EXPERIMENTS")
    print("=" * 65)
    thresholds = run_threshold_experiment(schedule, gt)
    for t in thresholds["threshold_experiments"]:
        print(f"  auto={t['auto_threshold']:.2f} review={t['review_threshold']:.2f}  "
              f"auto_linked={t['auto_linked']}  false_auto_rate={t['false_auto_link_rate']:.1f}%  "
              f"review={t['review']}  unmatched={t['unmatched']}")

    print("\n" + "=" * 65)
    print("  ERROR ANALYSIS")
    print("=" * 65)
    errors = run_error_analysis(schedule, gt)
    for cat, count in errors["error_categories"].items():
        if count > 0:
            print(f"  {cat}: {count}")
