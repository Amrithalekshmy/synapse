import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .matcher import SynapseMatchingEngine


app = FastAPI(
    title="SYNAPSE Matching Engine",
    description="Amritha's module — seven-layer hybrid matching of ExecutionEvents to ScheduleActivities",
    version="2.0.0",
)

_schedule_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "schedule.csv")
engine: SynapseMatchingEngine | None = None


def _get_engine() -> SynapseMatchingEngine:
    global engine
    if engine is None:
        engine = SynapseMatchingEngine(schedule_path=_schedule_path)
    return engine


class MatchRequest(BaseModel):
    event_text: str
    discipline: str | None = None
    location: str | None = None
    event_date: str | None = None
    top_k: int = 3


class BatchMatchRequest(BaseModel):
    events: list[dict]


class FeedbackRequest(BaseModel):
    event_id: str
    event_text: str
    correct_activity_id: str
    approved: bool


class ThresholdConfig(BaseModel):
    auto_threshold: float = 0.85
    review_threshold: float = 0.65


@app.get("/health")
def health():
    return {"status": "ok", "module": "matching_engine", "owner": "amritha"}


@app.post("/matches/run")
def run_match(req: MatchRequest):
    eng = _get_engine()
    result = eng.match_event(
        event_text=req.event_text,
        discipline=req.discipline,
        location=req.location,
        event_date=req.event_date,
        top_k=req.top_k,
    )
    return result


@app.post("/matches/batch")
def run_batch(req: BatchMatchRequest):
    eng = _get_engine()
    results = eng.process_batch(req.events)
    return {"results": results, "count": len(results)}


@app.post("/matches/feedback")
def submit_feedback(req: FeedbackRequest):
    eng = _get_engine()
    eng.record_feedback(req.event_id, req.event_text, req.correct_activity_id, req.approved)
    return {
        "status": "recorded",
        "event_id": req.event_id,
        "approved": req.approved,
        "total_feedback": len(eng.feedback_store),
    }


@app.post("/matches/feedback/save")
def save_feedback():
    eng = _get_engine()
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "feedback_store.json")
    eng.save_feedback(path)
    return {"status": "saved", "path": path, "count": len(eng.feedback_store)}


@app.post("/matches/feedback/load")
def load_feedback():
    eng = _get_engine()
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "feedback_store.json")
    eng.load_feedback(path)
    return {"status": "loaded", "count": len(eng.feedback_store)}


@app.get("/matches/review-queue")
def review_queue():
    eng = _get_engine()
    links = eng.get_review_queue()
    return {"queue": links, "count": len(links)}


@app.get("/matches/activity/{activity_id}/progress")
def activity_progress(activity_id: str):
    eng = _get_engine()
    progress = eng.get_activity_progress(activity_id)
    if not progress:
        raise HTTPException(404, f"No progress tracked for '{activity_id}'")
    return progress


@app.post("/matches/thresholds")
def update_thresholds(config: ThresholdConfig):
    eng = _get_engine()
    eng.auto_threshold = config.auto_threshold
    eng.review_threshold = config.review_threshold
    return {
        "auto_threshold": eng.auto_threshold,
        "review_threshold": eng.review_threshold,
    }


@app.post("/matches/activity/{activity_id}/complete")
def mark_complete(activity_id: str):
    eng = _get_engine()
    eng.mark_activity_completed(activity_id)
    return {"status": "marked_complete", "activity_id": activity_id}
