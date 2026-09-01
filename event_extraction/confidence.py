from event_extraction.models import ExecutionEvent, SourceType


FIELD_WEIGHTS = {
    "discipline": 0.15,
    "activity_type": 0.15,
    "asset": 0.20,
    "location": 0.10,
    "status": 0.15,
    "event_date": 0.10,
    "quantity": 0.05,
    "description": 0.10,
}

SOURCE_BONUS = {
    SourceType.DISCIPLINE_REPORT: 0.10,
    SourceType.EXCEL_SHEET: 0.10,
    SourceType.DAILY_REPORT: 0.05,
    SourceType.SUPERVISOR_MESSAGE: 0.0,
    SourceType.PDF_DOCUMENT: 0.03,
}


def score_confidence(event: ExecutionEvent) -> float:
    score = 0.0

    if event.discipline:
        score += FIELD_WEIGHTS["discipline"]
    if event.activity_type:
        score += FIELD_WEIGHTS["activity_type"]
    if event.asset:
        score += FIELD_WEIGHTS["asset"]
    if event.location:
        score += FIELD_WEIGHTS["location"]
    if event.status and event.status != "unknown":
        score += FIELD_WEIGHTS["status"]
    if event.event_date:
        score += FIELD_WEIGHTS["event_date"]
    if event.quantity is not None:
        score += FIELD_WEIGHTS["quantity"]

    desc = event.description or ""
    if desc and desc != event.raw_text and len(desc) > 10:
        score += FIELD_WEIGHTS["description"]

    bonus = SOURCE_BONUS.get(event.source_type, 0.0)
    score += bonus

    score = min(score, 0.99)
    return round(score, 2)
