"""
SYNAPSE Matching Engine
Amritha's module — matches ExecutionEvents to ScheduleActivities using NLP.

Seven-layer hybrid scoring:
  1. Semantic similarity (sentence-transformers or TF-IDF fallback)
  2. Identifier matching (asset IDs like FT-101, Line 24)
  3. Discipline matching
  4. Location matching
  5. WBS context (shared WBS lineage)
  6. Temporal context (event date vs planned window)
  7. Dependency context (predecessor completion awareness)

Plus: active learning feedback boosting, explanation generation,
      confidence-gated routing, agentic clarification.
"""

import re
import json
import os
from datetime import datetime
from difflib import SequenceMatcher

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

try:
    from sentence_transformers import SentenceTransformer
    USE_TRANSFORMER = True
except ImportError:
    from sklearn.feature_extraction.text import TfidfVectorizer
    USE_TRANSFORMER = False

from .explanation import generate_explanation
from .granularity import GranularityTracker


class SynapseMatchingEngine:

    def __init__(self, schedule_path=None, auto_threshold=0.85, review_threshold=0.65):
        if USE_TRANSFORMER:
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), analyzer="word")

        self.activities = []
        self.activity_embeddings = None
        self.feedback_store = []
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold
        self.granularity = GranularityTracker()

        self._activity_map: dict[str, dict] = {}
        self._wbs_tree: dict[str, list[str]] = {}
        self._completion_state: dict[str, str] = {}

        if schedule_path:
            self.load_schedule_file(schedule_path)

    # ------------------------------------------------------------------
    # LOADING ACTIVITIES
    # ------------------------------------------------------------------

    def load_schedule_file(self, path):
        """Load using Yazeen's ScheduleParser (supports Primavera XER/XML, MS Project, CSV)."""
        try:
            from schedule_parser import ScheduleParser
            parser = ScheduleParser()
            activities = parser.parse_to_amritha(path)
            self.load_activities(activities)
        except Exception:
            self.load_activities_from_csv(path)

    def load_activities_from_csv(self, path):
        """Fallback direct CSV loader."""
        df = pd.read_csv(path)
        self.activities = df.to_dict(orient="records")
        for a in self.activities:
            if isinstance(a.get("predecessors"), float) and pd.isna(a["predecessors"]):
                a["predecessors"] = ""
            if isinstance(a.get("successors"), float) and pd.isna(a["successors"]):
                a["successors"] = ""
        self._index_activities()
        self._encode_activities()

    def load_activities(self, activities_list):
        self.activities = activities_list
        self._index_activities()
        self._encode_activities()

    def _index_activities(self):
        self._activity_map = {a["activity_id"]: a for a in self.activities if "activity_id" in a}

        self._wbs_tree.clear()
        for a in self.activities:
            wbs = a.get("wbs_id", "")
            if wbs:
                self._wbs_tree.setdefault(wbs, []).append(a["activity_id"])

    def _activity_to_text(self, activity):
        parts = [
            activity.get("activity_name", ""),
            activity.get("discipline", ""),
            activity.get("location", ""),
        ]
        wbs = activity.get("wbs_id", "")
        if wbs:
            parts.append(wbs)
        return " ".join(str(p) for p in parts if p and str(p) != "nan")

    def _encode_activities(self):
        texts = [self._activity_to_text(a) for a in self.activities]
        if USE_TRANSFORMER:
            self.activity_embeddings = self.model.encode(texts, show_progress_bar=False)
        else:
            self.activity_embeddings = self.vectorizer.fit_transform(texts).toarray()

    # ------------------------------------------------------------------
    # SEVEN-LAYER HYBRID SCORING
    # ------------------------------------------------------------------

    def _boost_score(self, base_score, event_text, discipline, location, activity,
                     event_date=None, completed_predecessors=None):
        score = float(base_score)
        breakdown = {
            "semantic_score": float(base_score),
            "discipline_match": False,
            "location_match": False,
            "identifier_match": False,
            "wbs_boost": 0.0,
            "temporal_boost": 0.0,
            "dependency_boost": 0.0,
            "feedback_boost": 0.0,
            "event_discipline": discipline or "",
            "event_location": location or "",
        }

        # Layer 1: Semantic similarity is base_score (already computed)

        # Layer 2: Identifier matching (+0.20)
        identifiers = re.findall(
            r"\b[A-Z]+-\d+\b|\bLine\s+\d+\b|\bUnit\s+\d+\b|\bArea\s+[A-Z]\b",
            event_text, re.IGNORECASE,
        )
        activity_name = activity.get("activity_name", "")
        for ident in identifiers:
            if ident.upper() in activity_name.upper():
                score += 0.20
                breakdown["identifier_match"] = True
                break

        # Layer 3: Discipline match (+0.15)
        if discipline:
            if discipline.lower() == str(activity.get("discipline", "")).lower():
                score += 0.15
                breakdown["discipline_match"] = True

        # Layer 4: Location match (+0.10)
        if location:
            act_loc = str(activity.get("location", ""))
            if location.lower() in act_loc.lower():
                score += 0.10
                breakdown["location_match"] = True

        # Layer 5: WBS context (+0.05)
        wbs_boost = self._compute_wbs_boost(event_text, activity)
        score += wbs_boost
        breakdown["wbs_boost"] = wbs_boost

        # Layer 6: Temporal context (+0.05)
        temporal_boost = self._compute_temporal_boost(event_date, activity)
        score += temporal_boost
        breakdown["temporal_boost"] = temporal_boost

        # Layer 7: Dependency context (+0.05)
        dep_boost = self._compute_dependency_boost(activity, completed_predecessors)
        score += dep_boost
        breakdown["dependency_boost"] = dep_boost

        # Active learning boost
        fb_boost = self._compute_feedback_boost(event_text, activity)
        score += fb_boost
        breakdown["feedback_boost"] = fb_boost

        return min(score, 1.0), breakdown

    def _compute_wbs_boost(self, event_text, activity) -> float:
        wbs_id = activity.get("wbs_id", "")
        if not wbs_id:
            return 0.0

        identifiers = re.findall(r"\b[A-Z]+-\d+\b", event_text, re.IGNORECASE)
        if not identifiers:
            return 0.0

        for ident in identifiers:
            prefix = re.match(r"([A-Z]+)", ident, re.IGNORECASE)
            if prefix:
                p = prefix.group(1).upper()
                if wbs_id.upper().startswith(p[:3]):
                    return 0.05
        return 0.0

    def _compute_temporal_boost(self, event_date, activity) -> float:
        if not event_date:
            return 0.0
        planned_start = activity.get("planned_start", "")
        planned_finish = activity.get("planned_finish", "")
        if not planned_start or not planned_finish:
            return 0.0

        try:
            ev_dt = datetime.fromisoformat(str(event_date))
            start = datetime.fromisoformat(str(planned_start))
            finish = datetime.fromisoformat(str(planned_finish))
        except (ValueError, TypeError):
            return 0.0

        if start <= ev_dt <= finish:
            return 0.05
        delta_days = min(abs((ev_dt - start).days), abs((ev_dt - finish).days))
        if delta_days <= 7:
            return 0.02
        return 0.0

    def _compute_dependency_boost(self, activity, completed_predecessors=None) -> float:
        preds_raw = activity.get("predecessors", "")
        if not preds_raw or (isinstance(preds_raw, float)):
            return 0.03

        preds = [p.strip() for p in str(preds_raw).split(",") if p.strip()]
        if not preds:
            return 0.03

        if completed_predecessors is None:
            completed_predecessors = set(self._completion_state.keys())

        completed_count = sum(1 for p in preds if p in completed_predecessors)
        if completed_count == len(preds):
            return 0.05
        elif completed_count > 0:
            return 0.02
        return 0.0

    def _compute_feedback_boost(self, event_text, activity) -> float:
        if not self.feedback_store:
            return 0.0

        activity_id = activity.get("activity_id", "")
        event_lower = event_text.lower()
        boost = 0.0

        for fb in self.feedback_store:
            if fb.get("correct_activity_id") != activity_id:
                continue
            if not fb.get("approved", False):
                continue
            fb_text = fb.get("event_text", "").lower()
            similarity = SequenceMatcher(None, event_lower, fb_text).ratio()
            if similarity > 0.6:
                boost = max(boost, 0.10 * similarity)

        return round(boost, 4)

    # ------------------------------------------------------------------
    # AMBIGUITY DETECTION
    # ------------------------------------------------------------------

    def _is_ambiguous(self, event_text, top_candidates):
        has_identifier = bool(
            re.search(
                r"\b[A-Z]+-\d+\b|\bLine\s+\d+\b|\bUnit\s+\d+\b|\bArea\s+[A-Z]\b",
                event_text, re.IGNORECASE,
            )
        )

        scores_close = False
        if len(top_candidates) >= 2:
            gap = top_candidates[0][1] - top_candidates[1][1]
            scores_close = gap < 0.08

        word_count = len(event_text.strip().split())
        is_vague = word_count <= 6

        return is_vague and not has_identifier and scores_close

    def _generate_clarification_question(self, event_text, top_candidates):
        candidate_names = [c[0]["activity_name"] for c in top_candidates[:3]]
        options_str = "\n  - ".join(candidate_names)

        has_line = bool(re.search(r"\bline\b", event_text, re.IGNORECASE))
        has_unit = bool(re.search(r"\bunit\b|\barea\b", event_text, re.IGNORECASE))
        has_asset = bool(re.search(r"\b[A-Z]+-\d+\b", event_text, re.IGNORECASE))

        if not has_asset and not has_line:
            return (
                f"Which line or equipment does '{event_text}' refer to?\n"
                f"Possible matches:\n  - {options_str}"
            )
        elif not has_unit:
            return (
                f"Which unit or area did this happen in?\n"
                f"Possible matches:\n  - {options_str}"
            )
        else:
            return (
                f"Can you be more specific? Multiple activities match.\n"
                f"Possible matches:\n  - {options_str}"
            )

    # ------------------------------------------------------------------
    # CORE MATCH FUNCTION
    # ------------------------------------------------------------------

    def match_event(self, event_text, discipline=None, location=None,
                    event_date=None, completed_predecessors=None, top_k=3):
        if self.activity_embeddings is None:
            raise RuntimeError("No activities loaded. Call load_activities() first.")

        # Encode event
        if USE_TRANSFORMER:
            event_vec = self.model.encode([event_text])
        else:
            event_vec = self.vectorizer.transform([event_text]).toarray()
        raw_scores = cosine_similarity(event_vec, self.activity_embeddings)[0]

        # Top 10 by raw score → apply seven-layer boosting
        top_indices = raw_scores.argsort()[-10:][::-1]
        boosted = []
        breakdowns = []
        for i in top_indices:
            final, breakdown = self._boost_score(
                raw_scores[i], event_text, discipline, location,
                self.activities[i], event_date, completed_predecessors,
            )
            boosted.append((self.activities[i], final))
            breakdowns.append((self.activities[i], breakdown))

        boosted.sort(key=lambda x: x[1], reverse=True)
        breakdowns_sorted = sorted(breakdowns, key=lambda x: x[1].get("semantic_score", 0) + sum(
            x[1].get(k, 0) for k in ("wbs_boost", "temporal_boost", "dependency_boost", "feedback_boost")
        ), reverse=True)

        top = boosted[:top_k]
        best_activity, best_score = top[0]

        # Find the best breakdown for explanation
        best_breakdown = None
        for act, bd in breakdowns:
            if act["activity_id"] == best_activity["activity_id"]:
                best_breakdown = bd
                break

        explanation = generate_explanation(event_text, best_activity, best_breakdown or {})

        # Ambiguity check
        if self._is_ambiguous(event_text, top):
            return {
                "matched_activity_id": None,
                "matched_activity_name": None,
                "confidence": round(best_score, 3),
                "decision": "clarification_needed",
                "requires_clarification": True,
                "clarification_question": self._generate_clarification_question(event_text, top),
                "explanation": explanation,
                "candidates": [
                    {"activity_id": a["activity_id"], "name": a["activity_name"], "score": round(s, 3)}
                    for a, s in top
                ],
            }

        # Confidence-gated routing
        if best_score >= self.auto_threshold:
            decision = "auto_linked"
        elif best_score >= self.review_threshold:
            decision = "review"
        else:
            decision = "unmatched"

        return {
            "matched_activity_id": best_activity["activity_id"],
            "matched_activity_name": best_activity["activity_name"],
            "confidence": round(best_score, 3),
            "decision": decision,
            "requires_clarification": False,
            "clarification_question": None,
            "explanation": explanation,
            "candidates": [
                {"activity_id": a["activity_id"], "name": a["activity_name"], "score": round(s, 3)}
                for a, s in top
            ],
        }

    # ------------------------------------------------------------------
    # PROCESS EXECUTION EVENTS (Adithyan's format)
    # ------------------------------------------------------------------

    def _normalize_event(self, execution_event):
        if hasattr(execution_event, "model_dump"):
            execution_event = execution_event.model_dump()

        return {
            "event_id":    execution_event.get("event_id", "unknown"),
            "event_text":  execution_event.get("raw_text") or execution_event.get("description") or execution_event.get("event_text", ""),
            "discipline":  execution_event.get("discipline"),
            "location":    execution_event.get("location"),
            "date":        execution_event.get("event_date") or execution_event.get("date", "unknown"),
            "source":      execution_event.get("source_id") or execution_event.get("source", "unknown"),
            "status_hint": execution_event.get("status") or execution_event.get("status_hint", "unknown"),
        }

    def process_event(self, execution_event):
        ev = self._normalize_event(execution_event)
        result = self.match_event(
            event_text=ev["event_text"],
            discipline=ev.get("discipline"),
            location=ev.get("location"),
            event_date=ev.get("date"),
        )
        result["event_id"] = ev["event_id"]
        result["date"] = ev["date"]
        result["source"] = ev["source"]
        result["original_text"] = ev["event_text"]
        result["status_hint"] = ev["status_hint"]

        if result["matched_activity_id"] and result["decision"] == "auto_linked":
            self.granularity.record_link(
                ev["event_id"], result["matched_activity_id"],
                result["confidence"], ev["status_hint"],
            )

        return result

    def process_batch(self, execution_events):
        return [self.process_event(ev) for ev in execution_events]

    # ------------------------------------------------------------------
    # ACTIVE LEARNING — FEEDBACK
    # ------------------------------------------------------------------

    def record_feedback(self, event_id, event_text, correct_activity_id, approved):
        self.feedback_store.append({
            "event_id": event_id,
            "event_text": event_text,
            "correct_activity_id": correct_activity_id,
            "approved": approved,
        })

        if approved:
            self._completion_state[correct_activity_id] = "approved"

        self.granularity.record_link(
            event_id, correct_activity_id, 1.0 if approved else 0.0,
            "completed" if approved else "rejected",
        )

    def save_feedback(self, path="data/feedback_store.json"):
        with open(path, "w") as f:
            json.dump(self.feedback_store, f, indent=2)

    def load_feedback(self, path="data/feedback_store.json"):
        try:
            with open(path) as f:
                self.feedback_store = json.load(f)
        except FileNotFoundError:
            self.feedback_store = []

    def mark_activity_completed(self, activity_id: str):
        self._completion_state[activity_id] = "completed"

    # ------------------------------------------------------------------
    # MATCHING STATS
    # ------------------------------------------------------------------

    def get_review_queue(self) -> list[dict]:
        links = self.granularity.get_all_links()
        return [l for l in links]

    def get_activity_progress(self, activity_id: str) -> dict | None:
        return self.granularity.get_progress_summary(activity_id)
