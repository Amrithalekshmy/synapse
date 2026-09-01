import re
from datetime import date
from typing import Optional

from event_extraction.models import ExecutionEvent
from event_extraction.normalization import (
    normalize_status,
    normalize_activity_type,
    infer_discipline,
    extract_assets,
    extract_location,
    extract_quantity,
    normalize_date,
)


class RuleBasedExtractor:
    def extract(self, event: ExecutionEvent, reference_date: Optional[date] = None) -> ExecutionEvent:
        text = event.raw_text
        description = event.description

        if event.status == "unknown" or not event.status:
            event.status = self._extract_status(text) or "unknown"

        if not event.activity_type:
            event.activity_type = normalize_activity_type(text)

        if not event.discipline:
            event.discipline = self._extract_discipline(text, description)

        if not event.asset:
            event.asset = self._extract_primary_asset(text)

        if not event.location:
            event.location = extract_location(text)

        quantity, unit = extract_quantity(text)
        if quantity is not None and event.quantity is None:
            event.quantity = quantity
            event.unit = unit

        if event.event_date:
            resolved = normalize_date(event.event_date, reference_date)
            if resolved:
                event.event_date = resolved

        date_from_text = self._extract_date_from_text(text, reference_date)
        if date_from_text and not event.event_date:
            event.event_date = date_from_text

        event.event_type = self._determine_event_type(event)
        event.description = self._build_normalized_description(event)

        return event

    def _extract_status(self, text: str) -> Optional[str]:
        status = normalize_status(text)
        if status:
            return status
        text_lower = text.lower()
        if re.search(r'\b(?:still\s+pending|not\s+yet|awaiting|material\s+not)\b', text_lower):
            return "not_started"
        if re.search(r'\b(?:could\s+not|cannot|unable|faulty|failed)\b', text_lower):
            return "blocked"
        return None

    def _extract_discipline(self, text: str, description: str) -> Optional[str]:
        combined = f"{text} {description}"
        return infer_discipline(combined)

    def _extract_primary_asset(self, text: str) -> Optional[str]:
        assets = extract_assets(text)
        return assets[0] if assets else None

    def _extract_date_from_text(self, text: str, reference_date: Optional[date] = None) -> Optional[str]:
        return normalize_date(text, reference_date)

    def _determine_event_type(self, event: ExecutionEvent) -> str:
        status = event.status
        if status == "started":
            return "START"
        if status == "completed":
            return "COMPLETE"
        if status == "in_progress":
            if event.quantity is not None:
                return "QUANTITY_UPDATE"
            return "PROGRESS"
        if status in ("delayed", "blocked"):
            return "DELAY"
        if event.activity_type in ("inspection", "testing", "loop_check"):
            return "INSPECTION" if event.activity_type == "inspection" else "TEST"
        return "PROGRESS"

    def _build_normalized_description(self, event: ExecutionEvent) -> str:
        parts: list[str] = []
        if event.activity_type:
            parts.append(event.activity_type.replace("_", " ").title())
        if event.asset:
            parts.append(f"for {event.asset}")
        if event.location:
            parts.append(f"at {event.location}")
        if event.status and event.status != "unknown":
            parts.append(f"— {event.status}")

        if parts:
            return " ".join(parts)
        return event.raw_text
