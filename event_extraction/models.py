from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
import uuid


class EventStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NOT_STARTED = "not_started"
    DELAYED = "delayed"
    BLOCKED = "blocked"


class EventType(str, Enum):
    START = "START"
    PROGRESS = "PROGRESS"
    COMPLETE = "COMPLETE"
    INSPECTION = "INSPECTION"
    TEST = "TEST"
    DELAY = "DELAY"
    ISSUE = "ISSUE"
    QUANTITY_UPDATE = "QUANTITY_UPDATE"


class Discipline(str, Enum):
    CIVIL = "civil"
    PIPING = "piping"
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    INSTRUMENTATION = "instrumentation"
    STATIC_EQUIPMENT = "static_equipment"
    ROTATING_EQUIPMENT = "rotating_equipment"
    HSE = "hse"


class SourceType(str, Enum):
    DAILY_REPORT = "daily_report"
    DISCIPLINE_REPORT = "discipline_report"
    SUPERVISOR_MESSAGE = "supervisor_message"
    PDF_DOCUMENT = "pdf_document"
    EXCEL_SHEET = "excel_sheet"


def _generate_event_id() -> str:
    return f"EVT-{uuid.uuid4().hex[:6].upper()}"


class ExecutionEvent(BaseModel):
    event_id: str = Field(default_factory=_generate_event_id)
    source_id: str
    source_type: SourceType
    source_reference: Optional[str] = None
    raw_text: str
    description: str
    discipline: Optional[str] = None
    activity_type: Optional[str] = None
    asset: Optional[str] = None
    location: Optional[str] = None
    status: str
    event_type: Optional[str] = None
    event_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    extraction_confidence: float = 0.0


class ExtractionResult(BaseModel):
    events: list[ExecutionEvent]
    source_id: str
    source_type: SourceType
    warnings: list[str] = Field(default_factory=list)
    processing_time_ms: Optional[float] = None


class ClarificationRequest(BaseModel):
    event: ExecutionEvent
    missing_fields: list[str]
    question: str
    options: Optional[list[str]] = None


class ClarificationResponse(BaseModel):
    event_id: str
    selected_option: Optional[str] = None
    free_text: Optional[str] = None


class DuplicateGroup(BaseModel):
    primary_event_id: str
    duplicate_event_ids: list[str]
    similarity_score: float


class EvaluationMetrics(BaseModel):
    total_events: int = 0
    discipline_accuracy: float = 0.0
    asset_accuracy: float = 0.0
    status_accuracy: float = 0.0
    date_accuracy: float = 0.0
    activity_type_accuracy: float = 0.0
    location_accuracy: float = 0.0
    overall_field_accuracy: float = 0.0
    event_level_accuracy: float = 0.0
