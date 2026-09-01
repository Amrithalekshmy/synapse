"""
ProductivityTracker — discipline-level productivity benchmarking.
Adithyagopan's module.

Answers questions like:
  - What is the average spool erection rate for piping crews?
  - Which discipline consistently takes longer than planned?
  - Is the current project's observed rate below the historical average?

Usage
-----
    from knowledge_base.store import KnowledgeBase
    from knowledge_base.productivity import ProductivityTracker

    kb = KnowledgeBase()
    kb.load_csv("data/historical_knowledge_base.csv")

    tracker = ProductivityTracker(kb)
    bench = tracker.benchmark(discipline="piping", activity_type="erection")
    flag  = tracker.flag_below_average("piping", "erection", current_rate=2.1)
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from .models import ProductivityBenchmark, HistoricalRecord
from .store import KnowledgeBase


class ProductivityTracker:
    """
    Productivity benchmarking engine.

    Reads verified historical records and computes per-(discipline, activity_type)
    statistics. Compares current observed rates to historical averages.
    """

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    # ------------------------------------------------------------------
    # Benchmarking
    # ------------------------------------------------------------------

    def benchmark(
        self,
        discipline:     Optional[str] = None,
        activity_type:  Optional[str] = None,
        record_quality: str = "verified",
    ) -> ProductivityBenchmark:
        """
        Compute benchmark statistics for a discipline / activity_type pair.
        If neither supplied, computes over all records.
        """
        records = self.kb.filter(
            discipline=discipline,
            activity_type=activity_type,
            record_quality=record_quality,
        )
        return self._compute(discipline or "all", activity_type or "all", records)

    def all_benchmarks(self, record_quality: str = "verified") -> List[ProductivityBenchmark]:
        """Return one benchmark per (discipline, activity_type) combination."""
        records = self.kb.filter(record_quality=record_quality)
        groups: Dict[Tuple[str, str], List[HistoricalRecord]] = defaultdict(list)
        for r in records:
            groups[(r.discipline, r.activity_type)].append(r)

        results = []
        for (disc, atype), grp in sorted(groups.items()):
            results.append(self._compute(disc, atype, grp))
        return results

    def flag_below_average(
        self,
        discipline:        str,
        activity_type:     str,
        current_rate:      float,
        productivity_unit: Optional[str] = None,
    ) -> Dict:
        """
        Compare a current project's observed rate against historical average.

        Returns
        -------
        dict with: flagged, current_rate, avg_historical_rate, pct_below, message
        """
        bench = self.benchmark(discipline=discipline, activity_type=activity_type)

        if bench.avg_rate is None or bench.sample_count == 0:
            return {
                "flagged": False,
                "current_rate": current_rate,
                "avg_historical_rate": None,
                "message": "No historical data available for comparison.",
            }

        pct_below = round((bench.avg_rate - current_rate) / bench.avg_rate * 100, 1)
        flagged = pct_below > 10  # flag if >10% below avg

        unit = productivity_unit or bench.productivity_unit or ""
        if flagged:
            msg = (
                f"Current rate {current_rate} {unit} is {pct_below}% below historical "
                f"average of {bench.avg_rate} {unit}. Flag for planner attention."
            )
        else:
            msg = (
                f"Current rate {current_rate} {unit} is within acceptable range "
                f"of historical average {bench.avg_rate} {unit}."
            )

        return {
            "flagged":               flagged,
            "current_rate":          current_rate,
            "avg_historical_rate":   bench.avg_rate,
            "best_historical_rate":  bench.best_rate,
            "worst_historical_rate": bench.worst_rate,
            "pct_below":             pct_below,
            "productivity_unit":     unit,
            "sample_count":          bench.sample_count,
            "message":               msg,
        }

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @staticmethod
    def _compute(
        discipline:    str,
        activity_type: str,
        records:       List[HistoricalRecord],
    ) -> ProductivityBenchmark:
        bench = ProductivityBenchmark(
            discipline=discipline,
            activity_type=activity_type,
            sample_count=len(records),
        )
        if not records:
            return bench

        planned   = [r.planned_duration_days for r in records if r.planned_duration_days > 0]
        actual    = [r.actual_duration_days  for r in records if r.actual_duration_days  > 0]
        variances = [r.variance_days for r in records]
        delayed   = [r for r in records if r.delayed]

        bench.avg_planned_days  = round(sum(planned)   / len(planned),   2) if planned   else 0.0
        bench.avg_actual_days   = round(sum(actual)    / len(actual),    2) if actual    else 0.0
        bench.avg_variance_days = round(sum(variances) / len(variances), 2) if variances else 0.0
        bench.delay_frequency   = round(len(delayed) / len(records), 3)

        rates = [r.productivity_rate for r in records if r.productivity_rate is not None]
        units = [r.productivity_unit for r in records if r.productivity_unit]
        if rates:
            bench.avg_rate         = round(sum(rates) / len(rates), 3)
            bench.best_rate        = round(max(rates), 3)
            bench.worst_rate       = round(min(rates), 3)
            bench.productivity_unit = units[0] if units else None

        return bench
