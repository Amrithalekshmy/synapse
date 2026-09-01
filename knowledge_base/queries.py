"""
Built-in historical queries — minimum-version requirement.
Adithyagopan's module.

Implements the 5 useful historical queries from the spec:

  Q1 — How long did similar activities take?          (duration by discipline/type)
  Q2 — Which disciplines repeatedly experienced delays?
  Q3 — What were the most common causes of delay?
  Q4 — Which activities consistently exceeded baseline?
  Q5 — What is the delay risk for this current activity type?

Usage
-----
    from knowledge_base.store import KnowledgeBase
    from knowledge_base.queries import run_builtin_queries

    kb = KnowledgeBase()
    kb.load_csv("data/historical_knowledge_base.csv")
    results = run_builtin_queries(kb)
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from .store import KnowledgeBase


# ---------------------------------------------------------------------------
# Q1 — Duration statistics by discipline / activity_type
# ---------------------------------------------------------------------------

def q1_duration_by_type(
    kb: KnowledgeBase,
    discipline:     Optional[str] = None,
    activity_type:  Optional[str] = None,
    record_quality: str = "verified",
) -> Dict[str, Any]:
    """How long did similar activities take?"""
    records = kb.filter(
        discipline=discipline,
        activity_type=activity_type,
        record_quality=record_quality,
    )
    if not records:
        return {"error": "No matching records", "filters": {"discipline": discipline, "activity_type": activity_type}}

    groups: Dict[tuple, list] = defaultdict(list)
    for r in records:
        groups[(r.discipline, r.activity_type)].append(r)

    result = []
    for (disc, atype), grp in sorted(groups.items()):
        planned  = [r.planned_duration_days for r in grp if r.planned_duration_days > 0]
        actual   = [r.actual_duration_days  for r in grp if r.actual_duration_days  > 0]
        result.append({
            "discipline":        disc,
            "activity_type":     atype,
            "sample_count":      len(grp),
            "avg_planned_days":  round(sum(planned) / len(planned), 2) if planned else None,
            "avg_actual_days":   round(sum(actual)  / len(actual),  2) if actual  else None,
            "avg_variance_days": round(sum(r.variance_days for r in grp) / len(grp), 2),
            "delay_frequency":   round(sum(1 for r in grp if r.delayed) / len(grp), 3),
        })

    return {
        "query":   "How long did similar activities take?",
        "filters": {"discipline": discipline, "activity_type": activity_type},
        "results": result,
    }


# ---------------------------------------------------------------------------
# Q2 — Delay frequency by discipline
# ---------------------------------------------------------------------------

def q2_delay_by_discipline(
    kb: KnowledgeBase,
    record_quality: str = "verified",
) -> Dict[str, Any]:
    """Which disciplines repeatedly experienced delays?"""
    records = kb.filter(record_quality=record_quality)

    groups: Dict[str, list] = defaultdict(list)
    for r in records:
        groups[r.discipline].append(r)

    result = []
    for disc, grp in groups.items():
        n_delayed = sum(1 for r in grp if r.delayed)
        result.append({
            "discipline":       disc,
            "total_activities": len(grp),
            "delayed":          n_delayed,
            "delay_frequency":  round(n_delayed / len(grp), 3),
        })
    result.sort(key=lambda x: x["delay_frequency"], reverse=True)

    return {
        "query":   "Which disciplines repeatedly experienced delays?",
        "results": result,
    }


# ---------------------------------------------------------------------------
# Q3 — Common delay causes
# ---------------------------------------------------------------------------

def q3_common_causes(
    kb: KnowledgeBase,
    discipline:     Optional[str] = None,
    top_n:          int = 10,
    record_quality: str = "verified",
) -> Dict[str, Any]:
    """What were the most common causes of delay?"""
    records = kb.filter(
        discipline=discipline,
        delayed_only=True,
        record_quality=record_quality,
    )
    counter: Counter = Counter()
    for r in records:
        if r.delay_cause:
            counter[r.delay_cause] += 1

    total = len(records)
    result = [
        {
            "cause":     cause,
            "count":     count,
            "frequency": round(count / total, 3) if total else 0.0,
        }
        for cause, count in counter.most_common(top_n)
    ]

    return {
        "query":                "What were the most common causes of delay?",
        "filters":              {"discipline": discipline},
        "total_delayed_records": total,
        "results":              result,
    }


# ---------------------------------------------------------------------------
# Q4 — Activities that consistently exceed baseline
# ---------------------------------------------------------------------------

def q4_over_baseline(
    kb: KnowledgeBase,
    min_variance_days: int = 2,
    record_quality:    str = "verified",
) -> Dict[str, Any]:
    """Which activities consistently exceeded baseline duration?"""
    records = kb.filter(record_quality=record_quality)

    groups: Dict[tuple, list] = defaultdict(list)
    for r in records:
        groups[(r.discipline, r.activity_type)].append(r)

    result = []
    for (disc, atype), grp in groups.items():
        avg_var = sum(r.variance_days for r in grp) / len(grp)
        if avg_var >= min_variance_days:
            result.append({
                "discipline":          disc,
                "activity_type":       atype,
                "sample_count":        len(grp),
                "avg_variance_days":   round(avg_var, 2),
                "worst_variance_days": max(r.variance_days for r in grp),
                "delay_frequency":     round(sum(1 for r in grp if r.delayed) / len(grp), 3),
            })
    result.sort(key=lambda x: x["avg_variance_days"], reverse=True)

    return {
        "query":             "Which activities consistently exceeded baseline?",
        "min_variance_days": min_variance_days,
        "results":           result,
    }


# ---------------------------------------------------------------------------
# Q5 — Delay risk for a given activity type
# ---------------------------------------------------------------------------

def q5_risk_profile(
    kb:            KnowledgeBase,
    activity_type: str,
    discipline:    Optional[str] = None,
    record_quality: str = "verified",
) -> Dict[str, Any]:
    """What is the delay risk for this current activity type?"""
    from .risk import DelayRiskEngine
    engine = DelayRiskEngine(kb)
    result = engine.assess(
        activity_description=activity_type,
        discipline=discipline,
        activity_type=activity_type,
    )
    return {
        "query":       f"What is the delay risk for '{activity_type}'?",
        "discipline":  discipline,
        "risk_profile": result.model_dump() if hasattr(result, "model_dump") else result.dict(),
    }


# ---------------------------------------------------------------------------
# Run all five at once
# ---------------------------------------------------------------------------

def run_builtin_queries(kb: KnowledgeBase) -> Dict[str, Any]:
    """
    Execute all five built-in queries and return results keyed by name.

    Suitable for the demo: shows the full institutional memory capability in
    one call.
    """
    return {
        "Q1_duration_by_type":        q1_duration_by_type(kb),
        "Q2_delay_by_discipline":     q2_delay_by_discipline(kb),
        "Q3_common_delay_causes":     q3_common_causes(kb),
        "Q4_activities_over_baseline": q4_over_baseline(kb),
        "Q5_piping_erection_risk":    q5_risk_profile(
                                          kb,
                                          activity_type="erection",
                                          discipline="piping",
                                      ),
    }
