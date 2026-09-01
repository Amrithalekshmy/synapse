"""
NLQueryEngine — natural-language query layer over the KnowledgeBase.
Adithyagopan's module (strong version).

Accepts plain English questions and routes them to the correct built-in
query function or semantic search path via keyword/regex intent detection.

No LLM required — fully deterministic routing with graceful semantic fallback.

Usage
-----
    from knowledge_base.store import KnowledgeBase
    from knowledge_base.nlquery import NLQueryEngine

    kb = KnowledgeBase()
    kb.load_csv("data/historical_knowledge_base.csv")

    engine = NLQueryEngine(kb)
    print(engine.query("What usually delays piping erection?"))
    print(engine.query("How long does electrical cable pulling typically take?"))
    print(engine.query("Which discipline has the worst delay record?"))
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from .store import KnowledgeBase
from .queries import (
    q1_duration_by_type,
    q2_delay_by_discipline,
    q3_common_causes,
    q4_over_baseline,
    q5_risk_profile,
)

_DISCIPLINES = {
    "piping", "electrical", "civil", "instrumentation", "mechanical"
}

_ACTIVITY_TYPES = {
    "erection", "welding", "hydrotest", "insulation",
    "cable tray installation", "cable pulling", "termination", "panel installation",
    "excavation", "concreting", "backfilling",
    "instrument installation", "loop check",
    "equipment setting", "alignment", "commissioning",
    "valve installation",
}


class NLQueryEngine:
    """
    Natural-language query layer over the KnowledgeBase.

    Intent routing priority:
      1. Regex / keyword pattern matching (deterministic, fast)
      2. Semantic similarity search (generic fallback)
    """

    def __init__(self, kb: KnowledgeBase):
        self.kb = kb

    def query(self, question: str) -> Dict[str, Any]:
        """
        Answer a natural-language question about historical execution data.

        Returns
        -------
        {
            "question": str,
            "intent":   str,
            "params":   dict,
            "answer":   dict | list,    <- structured data
            "summary":  str,            <- human-readable one-liner
        }
        """
        intent, params = self._detect_intent(question)
        answer = self._route(intent, params)
        summary = self._summarise(intent, params, answer)
        return {
            "question": question,
            "intent":   intent,
            "params":   params,
            "answer":   answer,
            "summary":  summary,
        }

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def _detect_intent(self, question: str) -> tuple:
        q = question.lower()
        discipline   = self._extract_discipline(q)
        activity_type = self._extract_activity_type(q)

        if re.search(r"\b(cause|causes|why|reason|what.+delay)\b", q):
            return "delay_causes", {"discipline": discipline, "activity_type": activity_type}

        if re.search(r"\b(how long|duration|take|typical|average time|days)\b", q):
            return "duration_stats", {"discipline": discipline, "activity_type": activity_type}

        if re.search(r"\b(worst|most delay|high.+delay|discipline.*delay|delay.*discipline)\b", q):
            return "discipline_risk", {}

        if re.search(r"\b(similar|like|resembl|comparable|find.+historical|show.+histor)\b", q):
            return "similar_activities", {"query": question, "discipline": discipline}

        if re.search(r"\b(exceed|over.+baseline|longer than planned|baseline)\b", q):
            return "baseline_exceedance", {}

        if re.search(r"\b(risk|probability|chance.*delay|likely.*delay)\b", q):
            return "risk_profile", {"discipline": discipline, "activity_type": activity_type}

        if re.search(r"\b(productivity|rate|spools.+day|crew|output)\b", q):
            return "productivity", {"discipline": discipline, "activity_type": activity_type}

        return "generic_search", {"query": question}

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route(self, intent: str, params: dict) -> Any:
        if intent == "delay_causes":
            return q3_common_causes(self.kb, discipline=params.get("discipline"))

        if intent == "duration_stats":
            return q1_duration_by_type(
                self.kb,
                discipline=params.get("discipline"),
                activity_type=params.get("activity_type"),
            )

        if intent == "discipline_risk":
            return q2_delay_by_discipline(self.kb)

        if intent == "similar_activities":
            hits = self.kb.semantic_search(params.get("query", ""), top_k=5)
            return [
                {
                    "score":          h["score"],
                    "activity":       h["record"].activity_description,
                    "discipline":     h["record"].discipline,
                    "activity_type":  h["record"].activity_type,
                    "variance_days":  h["record"].variance_days,
                    "delayed":        h["record"].delayed,
                    "delay_cause":    h["record"].delay_cause,
                }
                for h in hits
            ]

        if intent == "baseline_exceedance":
            return q4_over_baseline(self.kb)

        if intent == "risk_profile":
            atype = params.get("activity_type") or "erection"
            return q5_risk_profile(
                self.kb,
                activity_type=atype,
                discipline=params.get("discipline"),
            )

        if intent == "productivity":
            from .productivity import ProductivityTracker
            bench = ProductivityTracker(self.kb).benchmark(
                discipline=params.get("discipline"),
                activity_type=params.get("activity_type"),
            )
            return bench.model_dump() if hasattr(bench, "model_dump") else bench.dict()

        # Generic fallback — semantic search
        hits = self.kb.semantic_search(params.get("query", ""), top_k=5)
        return hits

    # ------------------------------------------------------------------
    # Summary generation
    # ------------------------------------------------------------------

    def _summarise(self, intent: str, params: dict, answer: Any) -> str:
        disc  = params.get("discipline", "")
        atype = params.get("activity_type", "")
        prefix = f"{disc} {atype}".strip() or "all activities"

        try:
            if intent == "delay_causes":
                causes = answer.get("results", [])
                if causes:
                    top = causes[0]
                    return (
                        f"Top delay cause for {prefix}: '{top['cause']}' "
                        f"({top['frequency']*100:.0f}% of delayed cases)."
                    )
                return f"No delay causes found for {prefix}."

            if intent == "duration_stats":
                rows = answer.get("results", [])
                if rows:
                    r = rows[0]
                    return (
                        f"{r['discipline']} {r['activity_type']}: "
                        f"avg planned {r['avg_planned_days']}d, "
                        f"avg actual {r['avg_actual_days']}d "
                        f"(delay freq {r['delay_frequency']*100:.0f}%)."
                    )
                return f"No duration data found for {prefix}."

            if intent == "discipline_risk":
                rows = answer.get("results", [])
                if rows:
                    w = rows[0]
                    return (
                        f"Highest delay frequency: {w['discipline']} "
                        f"({w['delay_frequency']*100:.0f}% of activities delayed)."
                    )
                return "No discipline delay data found."

            if intent == "similar_activities":
                if answer:
                    top = answer[0]
                    return (
                        f"Best match: '{top['activity']}' "
                        f"(score {top['score']:.2f}, variance {top['variance_days']}d)."
                    )
                return "No similar activities found."

            if intent == "risk_profile":
                rp = answer.get("risk_profile", {})
                return (
                    f"{prefix} risk: {rp.get('risk_level', 'UNKNOWN')}. "
                    f"Historical delay freq: {rp.get('delay_frequency', 0)*100:.0f}%. "
                    f"Suggested buffer: {rp.get('suggested_buffer_days', 0)} day(s)."
                )

            if intent == "baseline_exceedance":
                rows = answer.get("results", [])
                if rows:
                    top = rows[0]
                    return (
                        f"Worst offender: {top['discipline']} {top['activity_type']} "
                        f"(avg +{top['avg_variance_days']}d over baseline)."
                    )
                return "No activities found that consistently exceed baseline."

        except Exception:
            pass

        return "Query completed. See 'answer' for details."

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_discipline(text: str) -> Optional[str]:
        for d in _DISCIPLINES:
            if d in text:
                return d
        return None

    @staticmethod
    def _extract_activity_type(text: str) -> Optional[str]:
        for atype in sorted(_ACTIVITY_TYPES, key=len, reverse=True):  # longest first
            if atype in text:
                return atype
        return None
