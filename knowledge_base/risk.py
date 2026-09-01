"""
DelayRiskEngine — forward-looking delay risk intelligence.
Adithyagopan's module.

Given a current activity description + discipline, the engine queries the
KnowledgeBase for similar completed activities and returns a DelayRiskResult
consumed by Adithyanbalu's risk scoring engine.

Usage
-----
    from knowledge_base.store import KnowledgeBase
    from knowledge_base.risk import DelayRiskEngine

    kb = KnowledgeBase()
    kb.load_csv("data/historical_knowledge_base.csv")

    engine = DelayRiskEngine(kb)
    result = engine.assess("Erect Line 24-XX", discipline="piping")
    print(result.risk_level, result.delay_frequency, result.suggested_buffer_days)
"""

from __future__ import annotations

import math
from typing import List, Optional

from .models import DelayCause, DelayRiskResult, HistoricalRecord
from .store import KnowledgeBase

# Thresholds
_HIGH_DELAY_FREQ   = 0.60   # >= 60% delayed -> HIGH
_MEDIUM_DELAY_FREQ = 0.35   # >= 35% delayed -> MEDIUM, else LOW
_HIGH_CONF_MIN     = 10     # >= 10 historical matches -> high confidence
_MED_CONF_MIN      = 4      # 4-9 matches -> medium confidence


class DelayRiskEngine:
    """
    Delay risk intelligence layer on top of KnowledgeBase.

    For each incoming current activity the engine:
      1. Retrieves best-matching historical records (filter then semantic widen)
      2. Computes statistical risk profile
      3. Returns a DelayRiskResult ready for Adithyanbalu's module
    """

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def assess(
        self,
        activity_description: str,
        discipline:           Optional[str] = None,
        activity_type:        Optional[str] = None,
        planned_duration_days: Optional[int] = None,
        top_k: int = 20,
    ) -> DelayRiskResult:
        """
        Assess delay risk for a current activity.

        Parameters
        ----------
        activity_description : free-text activity description
        discipline           : discipline filter (piping, electrical, ...)
        activity_type        : activity type filter (erection, welding, ...)
        planned_duration_days: planned duration of the current activity
        top_k                : max historical records to consider

        Returns
        -------
        DelayRiskResult
        """
        candidates = self._retrieve(activity_description, discipline, activity_type, top_k)

        if not candidates:
            return DelayRiskResult(
                query_activity=activity_description,
                discipline=discipline or "",
                activity_type=activity_type or "",
                historical_matches=0,
                risk_level="UNKNOWN",
                confidence="none",
            )

        stats = self.kb.delay_stats(candidates)
        causes = self._build_causes(stats["cause_counts"], len(candidates))
        buffer = self._buffer(stats["avg_variance_days"], stats["delay_frequency"])

        return DelayRiskResult(
            query_activity=activity_description,
            discipline=discipline or (candidates[0].discipline if candidates else ""),
            activity_type=activity_type or (candidates[0].activity_type if candidates else ""),
            historical_matches=len(candidates),
            avg_planned_duration_days=stats["avg_planned_days"],
            avg_actual_duration_days=stats["avg_actual_days"],
            avg_variance_days=stats["avg_variance_days"],
            delay_frequency=stats["delay_frequency"],
            common_delay_causes=causes,
            suggested_buffer_days=buffer,
            risk_level=self._risk_level(stats["delay_frequency"]),
            confidence=self._confidence(len(candidates)),
        )

    def batch_assess(
        self,
        activities: List[dict],
        top_k: int = 20,
    ) -> List[DelayRiskResult]:
        """Assess risk for a list of activity dicts."""
        return [
            self.assess(
                activity_description=a.get("activity_description", a.get("activity_name", "")),
                discipline=a.get("discipline"),
                activity_type=a.get("activity_type"),
                planned_duration_days=a.get("planned_duration_days") or a.get("duration_days"),
                top_k=top_k,
            )
            for a in activities
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _retrieve(
        self,
        query: str,
        discipline: Optional[str],
        activity_type: Optional[str],
        top_k: int,
    ) -> List[HistoricalRecord]:
        """Phase 1: narrow filter. Phase 2: widen via semantic search if sparse."""
        kw: dict = {"record_quality": "verified"}
        if discipline:
            kw["discipline"] = discipline
        if activity_type:
            kw["activity_type"] = activity_type

        exact = self.kb.filter(**kw)
        if len(exact) >= 3:
            return exact[:top_k]

        # Widen with semantic search
        hits = self.kb.semantic_search(query, top_k=top_k, quality_filter="verified")
        records = [h["record"] for h in hits]
        if discipline:
            records = [r for r in records if r.discipline.lower() == discipline.lower()]
        return records if records else exact

    @staticmethod
    def _build_causes(cause_counts: dict, total: int) -> List[DelayCause]:
        return [
            DelayCause(cause=c, count=n, frequency=round(n / total, 3) if total else 0.0)
            for c, n in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    @staticmethod
    def _buffer(avg_variance: float, delay_freq: float) -> int:
        if avg_variance <= 0:
            return 0
        base = math.ceil(avg_variance)
        if delay_freq >= _HIGH_DELAY_FREQ:
            base = max(base, math.ceil(avg_variance * 1.2))
        return max(0, base)

    @staticmethod
    def _risk_level(delay_freq: float) -> str:
        if delay_freq >= _HIGH_DELAY_FREQ:
            return "HIGH"
        elif delay_freq >= _MEDIUM_DELAY_FREQ:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _confidence(n: int) -> str:
        if n >= _HIGH_CONF_MIN:
            return "high"
        elif n >= _MED_CONF_MIN:
            return "medium"
        return "low"
