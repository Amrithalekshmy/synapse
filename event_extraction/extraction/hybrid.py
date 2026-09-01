from datetime import date
from typing import Optional

from event_extraction.models import ExecutionEvent
from event_extraction.extraction.rule_based import RuleBasedExtractor
from event_extraction.extraction.llm_extractor import LLMExtractor


class HybridExtractor:
    def __init__(self, use_llm: bool = False, llm_api_key: Optional[str] = None):
        self._rule_based = RuleBasedExtractor()
        self._use_llm = use_llm
        self._llm = LLMExtractor(api_key=llm_api_key) if use_llm else None

    def extract(self, event: ExecutionEvent, reference_date: Optional[date] = None) -> ExecutionEvent:
        event = self._rule_based.extract(event, reference_date)

        if self._should_use_llm(event) and self._llm and self._llm.available:
            saved_fields = {
                "discipline": event.discipline,
                "asset": event.asset,
                "location": event.location,
                "status": event.status if event.status != "unknown" else None,
                "activity_type": event.activity_type,
                "event_date": event.event_date,
                "quantity": event.quantity,
            }

            event = self._llm.extract_single(event)

            for field, value in saved_fields.items():
                if value is not None:
                    setattr(event, field, value)

        return event

    def _should_use_llm(self, event: ExecutionEvent) -> bool:
        missing = 0
        if not event.discipline:
            missing += 1
        if not event.asset:
            missing += 1
        if not event.activity_type:
            missing += 1
        if event.status == "unknown":
            missing += 1
        return missing >= 2
