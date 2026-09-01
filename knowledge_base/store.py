"""
KnowledgeBase — in-memory store for SYNAPSE historical records.
Adithyagopan's module.

Minimum-version responsibilities
---------------------------------
  • Load / insert historical records from CSV
  • Filter by discipline, project, quality, activity_type
  • Return records as HistoricalRecord objects
  • Persist to / restore from CSV (no PostgreSQL required for demo)

Strong-version hooks
--------------------
  • Semantic similarity search (sentence-transformers > TF-IDF > keyword fallback)
  • Delay statistics helper used by DelayRiskEngine

Usage
-----
    from knowledge_base.store import KnowledgeBase

    kb = KnowledgeBase()
    kb.load_csv("data/historical_knowledge_base.csv")
    records = kb.filter(discipline="piping", record_quality="verified")
"""

from __future__ import annotations

import csv
import os
import uuid
from typing import Any, Optional

from .models import HistoricalRecord

# Optional embedding libraries
try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    from sklearn.metrics.pairwise import cosine_similarity as _cos  # type: ignore
    import numpy as np  # type: ignore
    _USE_TRANSFORMERS = True
    _USE_TFIDF = False
except ImportError:
    _USE_TRANSFORMERS = False
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
        from sklearn.metrics.pairwise import cosine_similarity as _cos  # type: ignore
        _USE_TFIDF = True
    except ImportError:
        _USE_TFIDF = False


class KnowledgeBase:
    """
    Central store for verified historical execution records.

    All records live in self._records (list of HistoricalRecord).
    An embedding index is built lazily the first time semantic_search()
    is called.
    """

    def __init__(self):
        self._records: list[HistoricalRecord] = []
        self._model = None  # lazy-loaded sentence-transformer

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def insert(self, record: HistoricalRecord) -> str:
        """Insert a single HistoricalRecord. Returns its record_id."""
        if not record.record_id:
            record.record_id = str(uuid.uuid4())[:8]
        self._records.append(record)
        return record.record_id

    def bulk_insert(self, records: list[HistoricalRecord]) -> int:
        """Insert multiple records; returns count added."""
        for r in records:
            self.insert(r)
        return len(records)

    def load_csv(self, path: str) -> int:
        """
        Load historical records from CSV.

        Columns expected (matches data/historical_knowledge_base.csv):
          project_id, discipline, activity_type, activity_description,
          location_type, planned_duration_days, actual_duration_days,
          variance_days, delayed, delay_cause, record_quality
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"CSV not found: {path}")
        count = 0
        with open(path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.insert(self._row_to_record(row))
                count += 1
        return count

    def save_csv(self, path: str) -> int:
        """Persist all records to CSV."""
        if not self._records:
            return 0
        fieldnames = list(self._records[0].model_dump().keys())
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            for rec in self._records:
                w.writerow(rec.model_dump())
        return len(self._records)

    # ------------------------------------------------------------------
    # Querying / filtering
    # ------------------------------------------------------------------

    def all(self, quality: Optional[str] = None) -> list[HistoricalRecord]:
        if quality:
            return [r for r in self._records if r.record_quality == quality]
        return list(self._records)

    def filter(
        self,
        discipline:     Optional[str] = None,
        project_id:     Optional[str] = None,
        activity_type:  Optional[str] = None,
        record_quality: Optional[str] = None,
        delayed_only:   bool = False,
        location_type:  Optional[str] = None,
    ) -> list[HistoricalRecord]:
        """Exact-match filter across fields."""
        results = self._records
        if discipline:
            results = [r for r in results if r.discipline.lower() == discipline.lower()]
        if project_id:
            results = [r for r in results if r.project_id == project_id]
        if activity_type:
            results = [r for r in results if r.activity_type.lower() == activity_type.lower()]
        if record_quality:
            results = [r for r in results if r.record_quality == record_quality]
        if delayed_only:
            results = [r for r in results if r.delayed]
        if location_type:
            results = [r for r in results if r.location_type.lower() == location_type.lower()]
        return results

    def get_by_id(self, record_id: str) -> Optional[HistoricalRecord]:
        for r in self._records:
            if r.record_id == record_id:
                return r
        return None

    def mark_quality(self, record_id: str, quality: str) -> bool:
        r = self.get_by_id(record_id)
        if r:
            r.record_quality = quality
            return True
        return False

    # ------------------------------------------------------------------
    # Semantic similarity search (strong version)
    # ------------------------------------------------------------------

    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        quality_filter: str = "verified",
    ) -> list[dict[str, Any]]:
        """
        Find the most semantically similar historical records to *query*.

        Falls back gracefully: sentence-transformers > TF-IDF > keyword overlap.
        Returns list of {"record": HistoricalRecord, "score": float}.
        """
        candidates = self.filter(record_quality=quality_filter) if quality_filter else self._records
        if not candidates:
            return []

        texts = [self._record_text(r) for r in candidates]

        if _USE_TRANSFORMERS:
            scores = self._transformer_scores(query, texts)
        elif _USE_TFIDF:
            scores = self._tfidf_scores(query, texts)
        else:
            scores = self._keyword_scores(query, texts)

        paired = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        return [
            {"record": rec, "score": round(float(score), 4)}  # type: ignore[return-value]
            for score, rec in paired[:top_k]
        ]

    # ------------------------------------------------------------------
    # Statistics helper (used by DelayRiskEngine)
    # ------------------------------------------------------------------

    def delay_stats(self, records: list[HistoricalRecord]) -> dict[str, Any]:
        """Compute basic delay statistics over a list of records."""
        if not records:
            return {}
        n = len(records)
        n_delayed = sum(1 for r in records if r.delayed)
        variances = [r.variance_days for r in records]
        planned = [r.planned_duration_days for r in records if r.planned_duration_days > 0]
        actual  = [r.actual_duration_days  for r in records if r.actual_duration_days  > 0]

        cause_counts: dict[str, int] = {}
        for r in records:
            if r.delayed and r.delay_cause:
                cause_counts[r.delay_cause] = cause_counts.get(r.delay_cause, 0) + 1

        return {
            "count":            n,
            "n_delayed":        n_delayed,
            "delay_frequency":  round(n_delayed / n, 3),
            "avg_variance_days": round(sum(variances) / n, 2),
            "avg_planned_days": round(sum(planned) / len(planned), 2) if planned else 0,
            "avg_actual_days":  round(sum(actual)  / len(actual),  2) if actual  else 0,
            "cause_counts":     cause_counts,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_record(row: dict[str, str]) -> HistoricalRecord:
        def _int(v, d=0):
            try: return int(v)
            except: return d

        def _float(v):
            try: return float(v)
            except: return None

        def _bool(v):
            return str(v).strip().lower() in {"true", "1", "yes"}

        return HistoricalRecord(
            record_id=str(uuid.uuid4())[:8],
            project_id=row.get("project_id", "").strip(),
            activity_id=row.get("activity_id", "").strip(),
            activity_description=row.get("activity_description", "").strip(),
            discipline=row.get("discipline", "unknown").strip().lower(),
            activity_type=row.get("activity_type", "").strip().lower(),
            location_type=row.get("location_type", "").strip().lower(),
            planned_start=row.get("planned_start") or None,
            planned_finish=row.get("planned_finish") or None,
            actual_start=row.get("actual_start") or None,
            actual_finish=row.get("actual_finish") or None,
            planned_duration_days=_int(row.get("planned_duration_days", "0")),
            actual_duration_days=_int(row.get("actual_duration_days", "0")),
            variance_days=_int(row.get("variance_days", "0")),
            delayed=_bool(row.get("delayed", "false")),
            delay_cause=row.get("delay_cause", "").strip() or None,
            productivity_rate=_float(row.get("productivity_rate", "")),
            productivity_unit=row.get("productivity_unit", "").strip() or None,
            source_reference=row.get("source_reference", "").strip() or None,
            match_confidence=_float(row.get("match_confidence", "")),
            reviewer_status=row.get("reviewer_status", "").strip() or None,
            record_quality=row.get("record_quality", "provisional").strip(),
        )

    @staticmethod
    def _record_text(r: HistoricalRecord) -> str:
        return " ".join(filter(None, [
            r.activity_description,
            r.discipline,
            r.activity_type,
            r.location_type,
            r.delay_cause or "",
        ])).lower()

    def _transformer_scores(self, query: str, texts: list[str]) -> list[float]:
        if self._model is None:
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        q_emb = self._model.encode([query])
        t_emb = self._model.encode(texts)
        return _cos(q_emb, t_emb)[0].tolist()

    @staticmethod
    def _tfidf_scores(query: str, texts: list[str]) -> list[float]:
        vec = TfidfVectorizer(ngram_range=(1, 2)).fit_transform([query] + texts)
        return _cos(vec[0:1], vec[1:])[0].tolist()

    @staticmethod
    def _keyword_scores(query: str, texts: list[str]) -> list[float]:
        words = set(query.lower().split())
        scores = []
        for t in texts:
            tw = set(t.split())
            union = len(words | tw)
            scores.append(len(words & tw) / union if union else 0.0)
        return scores

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._records)

    def __repr__(self) -> str:
        return f"<KnowledgeBase records={len(self._records)}>"
