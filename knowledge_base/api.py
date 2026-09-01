"""
FastAPI router for the SYNAPSE Knowledge Base.
Adithyagopan's module — strong version API layer.

Mount in the main SYNAPSE FastAPI app:

    from knowledge_base.api import router as kb_router
    app.include_router(kb_router, prefix="/kb", tags=["Knowledge Base"])

Endpoints
---------
POST  /kb/records                  Insert a single record
POST  /kb/records/bulk             Bulk insert records
GET   /kb/records                  List / filter records
GET   /kb/records/{id}             Get single record
PATCH /kb/records/{id}/quality     Update record quality

GET   /kb/risk                     Delay risk for a current activity
GET   /kb/productivity             Productivity benchmark
GET   /kb/queries/run              Run all 5 built-in queries
POST  /kb/search                   Natural-language query
GET   /kb/search/semantic          Semantic similarity search
GET   /kb/stats                    Knowledge base statistics
"""

from __future__ import annotations

import csv
import io
import os
from typing import List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query, UploadFile, File
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

from .models import HistoricalRecord, RecordQuality
from .store import KnowledgeBase
from .risk import DelayRiskEngine
from .productivity import ProductivityTracker
from .queries import run_builtin_queries
from .nlquery import NLQueryEngine

# ---------------------------------------------------------------------------
# Singleton KB — replace with dependency injection in production
# ---------------------------------------------------------------------------

_KB_CSV = os.path.join(
    os.path.dirname(__file__), "..", "data", "historical_knowledge_base.csv"
)
_kb: Optional[KnowledgeBase] = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
        if os.path.exists(_KB_CSV):
            _kb.load_csv(_KB_CSV)
    return _kb


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if not _HAS_FASTAPI:
    router = None  # type: ignore
else:
    router = APIRouter()

    # -----------------------------------------------------------------------
    # Records CRUD
    # -----------------------------------------------------------------------

    @router.post("/records", summary="Insert a historical record")
    def insert_record(record: HistoricalRecord):
        rid = get_kb().insert(record)
        return {"record_id": rid, "message": "Record inserted."}

    @router.post("/records/bulk", summary="Bulk insert historical records")
    def bulk_insert(records: List[HistoricalRecord]):
        n = get_kb().bulk_insert(records)
        return {"inserted": n}

    @router.post("/records/upload-csv", summary="Upload CSV of historical records")
    async def upload_csv(file: UploadFile = File(...)):
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        records = [KnowledgeBase._row_to_record(row) for row in reader]
        n = get_kb().bulk_insert(records)
        return {"inserted": n, "total_in_kb": len(get_kb())}

    @router.get("/records", summary="List / filter records")
    def list_records(
        discipline:     Optional[str] = Query(None),
        project_id:     Optional[str] = Query(None),
        activity_type:  Optional[str] = Query(None),
        record_quality: Optional[str] = Query(None),
        delayed_only:   bool          = Query(False),
        limit:          int           = Query(100, ge=1, le=1000),
    ):
        records = get_kb().filter(
            discipline=discipline,
            project_id=project_id,
            activity_type=activity_type,
            record_quality=record_quality,
            delayed_only=delayed_only,
        )
        return {
            "total":   len(records),
            "records": [r.model_dump() for r in records[:limit]],
        }

    @router.get("/records/{record_id}", summary="Get a single historical record")
    def get_record(record_id: str):
        r = get_kb().get_by_id(record_id)
        if not r:
            raise HTTPException(status_code=404, detail="Record not found")
        return r.model_dump()

    @router.patch("/records/{record_id}/quality", summary="Update record quality")
    def update_quality(record_id: str, quality: RecordQuality):
        ok = get_kb().mark_quality(record_id, quality.value)
        if not ok:
            raise HTTPException(status_code=404, detail="Record not found")
        return {"record_id": record_id, "quality": quality.value}

    # -----------------------------------------------------------------------
    # Delay risk (primary output for Adithyanbalu)
    # -----------------------------------------------------------------------

    @router.get("/risk", summary="Delay risk for a current activity")
    def delay_risk(
        activity_description:  str            = Query(...),
        discipline:            Optional[str]  = Query(None),
        activity_type:         Optional[str]  = Query(None),
        planned_duration_days: Optional[int]  = Query(None),
    ):
        engine = DelayRiskEngine(get_kb())
        result = engine.assess(
            activity_description=activity_description,
            discipline=discipline,
            activity_type=activity_type,
            planned_duration_days=planned_duration_days,
        )
        return result.model_dump()

    # -----------------------------------------------------------------------
    # Productivity
    # -----------------------------------------------------------------------

    @router.get("/productivity", summary="Productivity benchmark")
    def productivity(
        discipline:        Optional[str]   = Query(None),
        activity_type:     Optional[str]   = Query(None),
        current_rate:      Optional[float] = Query(None),
        productivity_unit: Optional[str]   = Query(None),
    ):
        tracker = ProductivityTracker(get_kb())
        if current_rate is not None and discipline and activity_type:
            return tracker.flag_below_average(
                discipline=discipline,
                activity_type=activity_type,
                current_rate=current_rate,
                productivity_unit=productivity_unit,
            )
        bench = tracker.benchmark(discipline=discipline, activity_type=activity_type)
        return bench.model_dump()

    # -----------------------------------------------------------------------
    # Built-in queries
    # -----------------------------------------------------------------------

    @router.get("/queries/run", summary="Run all 5 built-in historical queries")
    def run_queries():
        return run_builtin_queries(get_kb())

    # -----------------------------------------------------------------------
    # Natural-language search
    # -----------------------------------------------------------------------

    @router.post("/search", summary="Natural-language query over historical records")
    def nl_search(body: dict):
        question = body.get("question", "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="'question' is required")
        return NLQueryEngine(get_kb()).query(question)

    @router.get("/search/semantic", summary="Semantic similarity search")
    def semantic_search(
        q:              str           = Query(...),
        top_k:          int           = Query(5, ge=1, le=20),
        quality_filter: Optional[str] = Query("verified"),
    ):
        hits = get_kb().semantic_search(q, top_k=top_k, quality_filter=quality_filter)
        return {
            "query": q,
            "hits": [
                {"score": h["score"], "record": h["record"].model_dump()}
                for h in hits
            ],
        }

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    @router.get("/stats", summary="Knowledge base statistics")
    def stats():
        kb = get_kb()
        all_r = kb.all()
        by_disc: dict = {}
        for r in all_r:
            by_disc[r.discipline] = by_disc.get(r.discipline, 0) + 1
        return {
            "total_records": len(all_r),
            "verified":      sum(1 for r in all_r if r.record_quality == "verified"),
            "provisional":   sum(1 for r in all_r if r.record_quality == "provisional"),
            "rejected":      sum(1 for r in all_r if r.record_quality == "rejected"),
            "total_delayed": sum(1 for r in all_r if r.delayed),
            "by_discipline": by_disc,
        }
