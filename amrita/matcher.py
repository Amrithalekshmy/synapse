"""
SYNAPSE Matching Engine
Amritha's module — matches ExecutionEvents to ScheduleActivities using NLP.

Inputs:
    - Schedule activities (from Yazeen's parser, or schedule.csv for testing)
    - Execution events  (from Adithyan's extractor, or ground_truth.json for testing)

Output:
    - MatchResult dict per event
"""

import re
import json
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Try sentence-transformers, fall back to TF-IDF if not installed
try:
    from sentence_transformers import SentenceTransformer
    USE_TRANSFORMER = True
    print("[SYNAPSE] Using sentence-transformers (semantic mode)")
except ImportError:
    from sklearn.feature_extraction.text import TfidfVectorizer
    USE_TRANSFORMER = False
    print("[SYNAPSE] sentence-transformers not found — using TF-IDF mode")


class SynapseMatchingEngine:

    def __init__(self, schedule_path=None):
        if USE_TRANSFORMER:
            print("[SYNAPSE] Loading NLP model... (first time ~30 seconds)")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        else:
            self.vectorizer = TfidfVectorizer(ngram_range=(1, 2), analyzer="word")

        self.activities = []
        self.activity_embeddings = None
        self.feedback_store = []

        if schedule_path:
            self.load_activities_from_csv(schedule_path)

    # ------------------------------------------------------------------
    # LOADING ACTIVITIES
    # ------------------------------------------------------------------

    def load_activities_from_csv(self, path):
        """Load from schedule.csv — used for testing without Yazeen's code."""
        df = pd.read_csv(path)
        self.activities = df.to_dict(orient="records")
        self._encode_activities()

    def load_activities(self, activities_list):
        """
        Called by Yazeen's module when his parser runs on a real P6 file.
        activities_list: list of dicts with keys:
            activity_id, activity_name, discipline, location, planned_start, planned_finish
        """
        self.activities = activities_list
        self._encode_activities()

    def _activity_to_text(self, activity):
        return (
            f"{activity['activity_name']} "
            f"{activity['discipline']} "
            f"{activity['location']}"
        )

    def _encode_activities(self):
        texts = [self._activity_to_text(a) for a in self.activities]
        if USE_TRANSFORMER:
            self.activity_embeddings = self.model.encode(texts, show_progress_bar=False)
        else:
            self.activity_embeddings = self.vectorizer.fit_transform(texts).toarray()
        print(f"[SYNAPSE] {len(self.activities)} activities loaded and encoded.")

    # ------------------------------------------------------------------
    # HYBRID SCORING
    # ------------------------------------------------------------------

    def _boost_score(self, base_score, event_text, discipline, location, activity):
        score = float(base_score)

        # Boost 1: Discipline match (+0.15)
        if discipline:
            if discipline.lower() == activity.get("discipline", "").lower():
                score += 0.15

        # Boost 2: Location match (+0.10)
        if location:
            if location.lower() in activity.get("location", "").lower():
                score += 0.10

        # Boost 3: Asset/identifier match (+0.20)
        # Matches things like "FT-101", "P-101", "Line 24", "K-201"
        identifiers = re.findall(
            r"\b[A-Z]+-\d+\b|\bLine\s+\d+\b|\bUnit\s+\d+\b|\bArea\s+[A-Z]\b",
            event_text,
            re.IGNORECASE,
        )
        activity_name = activity.get("activity_name", "")
        for ident in identifiers:
            if ident.upper() in activity_name.upper():
                score += 0.20
                break

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # AMBIGUITY DETECTION
    # ------------------------------------------------------------------

    def _is_ambiguous(self, event_text, top_candidates):
        """
        Returns True when the event is too vague to auto-link.
        Two conditions must both be true:
          1. No specific identifier (line number, asset ID, location) found
          2. Top two candidate scores are very close (engine is uncertain)
        """
        has_identifier = bool(
            re.search(
                r"\b[A-Z]+-\d+\b|\bLine\s+\d+\b|\bUnit\s+\d+\b|\bArea\s+[A-Z]\b",
                event_text,
                re.IGNORECASE,
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
        """Build a targeted question to send to the supervisor."""
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

    def match_event(self, event_text, discipline=None, location=None, top_k=3):
        """
        Match a single event text to the best planned activity.

        Args:
            event_text  : str  — the raw event description
            discipline  : str  — optional, e.g. "piping", "electrical"
            location    : str  — optional, e.g. "Unit 4", "Area B"
            top_k       : int  — how many candidates to return

        Returns:
            MatchResult dict with keys:
                matched_activity_id, matched_activity_name,
                confidence, decision, requires_clarification,
                clarification_question, candidates
        """
        if self.activity_embeddings is None:
            raise RuntimeError("No activities loaded. Call load_activities() first.")

        # Step 1 — encode event and compute similarity
        if USE_TRANSFORMER:
            event_vec = self.model.encode([event_text])
        else:
            event_vec = self.vectorizer.transform([event_text]).toarray()
        raw_scores = cosine_similarity(event_vec, self.activity_embeddings)[0]

        # Step 2 — take top 10 by raw score, then apply boosts
        top_indices = raw_scores.argsort()[-10:][::-1]
        boosted = []
        for i in top_indices:
            final = self._boost_score(
                raw_scores[i], event_text, discipline, location, self.activities[i]
            )
            boosted.append((self.activities[i], final))

        # Step 3 — sort by boosted score, keep top_k
        boosted.sort(key=lambda x: x[1], reverse=True)
        top = boosted[:top_k]

        best_activity, best_score = top[0]

        # Step 4 — check if event is too ambiguous
        if self._is_ambiguous(event_text, top):
            return {
                "matched_activity_id": None,
                "matched_activity_name": None,
                "confidence": round(best_score, 3),
                "decision": "clarification_needed",
                "requires_clarification": True,
                "clarification_question": self._generate_clarification_question(event_text, top),
                "candidates": [
                    {
                        "activity_id": a["activity_id"],
                        "name": a["activity_name"],
                        "score": round(s, 3),
                    }
                    for a, s in top
                ],
            }

        # Step 5 — apply confidence threshold
        if best_score >= 0.85:
            decision = "auto_linked"
        elif best_score >= 0.65:
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
            "candidates": [
                {
                    "activity_id": a["activity_id"],
                    "name": a["activity_name"],
                    "score": round(s, 3),
                }
                for a, s in top
            ],
        }

    # ------------------------------------------------------------------
    # PROCESS A FULL EXECUTION EVENT (Adithyan's format)
    # ------------------------------------------------------------------

    def _normalize_event(self, execution_event):
        """
        Adapter for Adithyan's ExecutionEvent format.
        His field names differ slightly from our internal keys — map them here.
        Supports both dict and Pydantic model (via .model_dump()).
        """
        if hasattr(execution_event, "model_dump"):
            execution_event = execution_event.model_dump()

        return {
            "event_id":   execution_event.get("event_id", "unknown"),
            "event_text": execution_event.get("raw_text") or execution_event.get("description") or execution_event.get("event_text", ""),
            "discipline": execution_event.get("discipline"),
            "location":   execution_event.get("location"),
            "date":       execution_event.get("event_date") or execution_event.get("date", "unknown"),
            "source":     execution_event.get("source_id") or execution_event.get("source", "unknown"),
            "status_hint":execution_event.get("status") or execution_event.get("status_hint", "unknown"),
        }

    def process_event(self, execution_event):
        """
        Accepts Adithyan's ExecutionEvent (Pydantic model or dict).
        Returns a MatchResult dict with event metadata attached.
        """
        ev = self._normalize_event(execution_event)
        result = self.match_event(
            event_text=ev["event_text"],
            discipline=ev.get("discipline"),
            location=ev.get("location"),
        )
        result["event_id"]      = ev["event_id"]
        result["date"]          = ev["date"]
        result["source"]        = ev["source"]
        result["original_text"] = ev["event_text"]
        result["status_hint"]   = ev["status_hint"]
        return result

    def process_batch(self, execution_events):
        """Process a list of ExecutionEvents and return all MatchResults."""
        return [self.process_event(ev) for ev in execution_events]

    # ------------------------------------------------------------------
    # ACTIVE LEARNING — FEEDBACK
    # ------------------------------------------------------------------

    def record_feedback(self, event_id, event_text, correct_activity_id, approved):
        """
        Called when a human reviewer approves or rejects a match.

        approved=True  — the match was correct, reinforce it
        approved=False — the match was wrong, correct_activity_id is the right one
        """
        self.feedback_store.append({
            "event_id": event_id,
            "event_text": event_text,
            "correct_activity_id": correct_activity_id,
            "approved": approved,
        })
        action = "APPROVED" if approved else "CORRECTED"
        print(
            f"[ACTIVE LEARNING] {action} — event '{event_id}' → activity '{correct_activity_id}'. "
            f"Total feedback stored: {len(self.feedback_store)}"
        )

    def save_feedback(self, path="data/feedback_store.json"):
        with open(path, "w") as f:
            json.dump(self.feedback_store, f, indent=2)
        print(f"[ACTIVE LEARNING] Feedback saved to {path}")

    def load_feedback(self, path="data/feedback_store.json"):
        try:
            with open(path) as f:
                self.feedback_store = json.load(f)
            print(f"[ACTIVE LEARNING] Loaded {len(self.feedback_store)} feedback records.")
        except FileNotFoundError:
            print("[ACTIVE LEARNING] No feedback file found. Starting fresh.")
