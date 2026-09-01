from dataclasses import dataclass
from datetime import date


@dataclass
class MatchedEvent:
    event_id: str
    activity_id: str
    event_date: date
    confidence: float
    decision: str
    status_hint: str
    original_text: str