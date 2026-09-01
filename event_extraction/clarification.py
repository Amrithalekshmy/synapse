from typing import Optional

from event_extraction.models import ExecutionEvent, ClarificationRequest


CRITICAL_FIELDS = ["asset", "discipline", "status"]
IMPORTANT_FIELDS = ["location", "activity_type"]


def needs_clarification(event: ExecutionEvent) -> bool:
    if event.extraction_confidence >= 0.80:
        return False
    missing_critical = sum(
        1 for f in CRITICAL_FIELDS
        if getattr(event, f) is None or (f == "status" and getattr(event, f) == "unknown")
    )
    return missing_critical >= 1


def generate_clarification(
    event: ExecutionEvent,
    active_activities: Optional[list[dict]] = None,
) -> Optional[ClarificationRequest]:
    if not needs_clarification(event):
        return None

    missing: list[str] = []
    for field in CRITICAL_FIELDS + IMPORTANT_FIELDS:
        value = getattr(event, field, None)
        if value is None or (field == "status" and value == "unknown"):
            missing.append(field)

    if not missing:
        return None

    question, options = _build_question(event, missing, active_activities)

    return ClarificationRequest(
        event=event,
        missing_fields=missing,
        question=question,
        options=options,
    )


def _build_question(
    event: ExecutionEvent,
    missing: list[str],
    active_activities: Optional[list[dict]] = None,
) -> tuple[str, Optional[list[str]]]:
    if "asset" in missing and active_activities:
        candidates = _filter_candidates(event, active_activities)
        if candidates:
            options = [
                f"{c.get('activity_id', '?')} — {c.get('activity_name', '?')}"
                for c in candidates[:5]
            ]
            desc = event.activity_type or "activity"
            return (
                f'I found multiple {desc} activities that could match "{event.raw_text}". '
                f"Which one did you mean?",
                options,
            )
        return (
            f'Which asset/line does this refer to: "{event.raw_text}"?',
            None,
        )

    if "asset" in missing:
        return (
            f'Which asset or line does this refer to: "{event.raw_text}"?',
            None,
        )

    if "discipline" in missing:
        return (
            f'Which discipline does this belong to: "{event.raw_text}"? '
            "(piping / electrical / civil / instrumentation / mechanical)",
            ["piping", "electrical", "civil", "instrumentation", "mechanical"],
        )

    if "status" in missing:
        return (
            f'What is the current status of: "{event.raw_text}"?',
            ["started", "in_progress", "completed"],
        )

    if "location" in missing:
        return (
            f'Which area or unit does this relate to: "{event.raw_text}"?',
            None,
        )

    return (
        f'Could you provide more detail about: "{event.raw_text}"?',
        None,
    )


def apply_clarification(
    event: ExecutionEvent,
    field: str,
    value: str,
) -> ExecutionEvent:
    if field in ("asset", "discipline", "activity_type", "location"):
        setattr(event, field, value)
    elif field == "status":
        event.status = value
    event.extraction_confidence = min(event.extraction_confidence + 0.15, 0.99)
    return event


def _filter_candidates(event: ExecutionEvent, activities: list[dict]) -> list[dict]:
    filtered = activities
    if event.discipline:
        filtered = [a for a in filtered if a.get("discipline", "").lower() == event.discipline]
    if event.location:
        filtered = [a for a in filtered if event.location.lower() in a.get("location", "").lower()]
    if event.activity_type:
        type_lower = event.activity_type.lower()
        filtered = [
            a for a in filtered
            if type_lower in a.get("activity_name", "").lower()
        ]
    return filtered if filtered else activities[:5]
