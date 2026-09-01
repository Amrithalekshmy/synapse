import os
import tempfile
from datetime import date
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from event_extraction.models import (
    ExtractionResult,
    SourceType,
    ClarificationRequest,
    ClarificationResponse,
    DuplicateGroup,
    EvaluationMetrics,
)
from event_extraction.pipeline import ExtractionPipeline
from event_extraction.clarification import apply_clarification
from event_extraction.evaluation import run_evaluation

app = FastAPI(
    title="SYNAPSE Event Extraction",
    description="Heterogeneous Data Ingestion & Activity Event Extraction for EPC projects",
    version="1.0.0",
)

pipeline = ExtractionPipeline(
    use_llm=bool(os.environ.get("ANTHROPIC_API_KEY")),
)

_event_store: dict[str, ExtractionResult] = {}


class TextExtractionRequest(BaseModel):
    text: str
    source_id: Optional[str] = None
    source_type: str = "supervisor_message"
    reference_date: Optional[str] = None


class ClarifyRequest(BaseModel):
    event_id: str
    field: str
    value: str


class EvalResponse(BaseModel):
    total_events_extracted: int
    metrics: EvaluationMetrics


@app.get("/health")
def health():
    return {"status": "ok", "module": "event_extraction", "version": "1.0.0"}


@app.post("/events/extract", response_model=ExtractionResult)
async def extract_from_file(
    file: UploadFile = File(...),
    source_id: Optional[str] = Form(None),
    reference_date: Optional[str] = Form(None),
):
    suffix = os.path.splitext(file.filename or "upload.txt")[1]
    ref_date = None
    if reference_date:
        try:
            ref_date = date.fromisoformat(reference_date)
        except ValueError:
            raise HTTPException(400, "Invalid reference_date format — use YYYY-MM-DD")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = pipeline.process_file(tmp_path, source_id=source_id, reference_date=ref_date)
    finally:
        os.unlink(tmp_path)

    _event_store[result.source_id] = result
    return result


@app.post("/events/extract/text", response_model=ExtractionResult)
def extract_from_text(request: TextExtractionRequest):
    try:
        src_type = SourceType(request.source_type)
    except ValueError:
        src_type = SourceType.SUPERVISOR_MESSAGE

    ref_date = None
    if request.reference_date:
        try:
            ref_date = date.fromisoformat(request.reference_date)
        except ValueError:
            raise HTTPException(400, "Invalid reference_date format — use YYYY-MM-DD")

    result = pipeline.process_text(
        text=request.text,
        source_id=request.source_id or "text_input",
        source_type=src_type,
        reference_date=ref_date,
    )
    _event_store[result.source_id] = result
    return result


@app.get("/events", response_model=list[ExtractionResult])
def list_events():
    return list(_event_store.values())


@app.get("/events/{source_id}", response_model=ExtractionResult)
def get_events(source_id: str):
    if source_id not in _event_store:
        raise HTTPException(404, f"No events found for source: {source_id}")
    return _event_store[source_id]


@app.post("/events/clarify")
def clarify_event(request: ClarifyRequest):
    for result in _event_store.values():
        for event in result.events:
            if event.event_id == request.event_id:
                updated = apply_clarification(event, request.field, request.value)
                return {"status": "updated", "event": updated.model_dump()}
    raise HTTPException(404, f"Event not found: {request.event_id}")


@app.post("/events/clarification-requests", response_model=list[ClarificationRequest])
def get_clarification_requests():
    all_events = []
    for result in _event_store.values():
        all_events.extend(result.events)
    return pipeline.get_clarification_requests(all_events)


@app.post("/events/duplicates", response_model=list[DuplicateGroup])
def find_duplicate_events(threshold: float = 0.80):
    all_events = []
    for result in _event_store.values():
        all_events.extend(result.events)
    return pipeline.find_duplicates(all_events, threshold)


@app.post("/events/evaluate", response_model=EvalResponse)
def evaluate(data_dir: str = "data"):
    result = run_evaluation(data_dir=data_dir)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
