from dataclasses import dataclass
from typing import Optional


@dataclass
class Conflict:
    conflict_type: str
    message: str
    severity: str


def detect_date_conflict(
    planned_finish,
    actual_finish,
) -> Optional[Conflict]:
    """Detect when actual completion happened after the planned finish."""

    if planned_finish is None or actual_finish is None:
        return None

    if actual_finish > planned_finish:
        days_late = (actual_finish - planned_finish).days

        return Conflict(
            conflict_type="DATE_DELAY",
            message=f"Activity finished {days_late} day(s) later than planned.",
            severity="HIGH" if days_late > 7 else "MEDIUM",
        )

    return None


def detect_status_conflict(
    schedule_status: str,
    execution_status: str,
) -> Optional[Conflict]:
    """Detect contradictory schedule and execution statuses."""

    if not schedule_status or not execution_status:
        return None

    schedule = schedule_status.upper()
    execution = execution_status.upper()

    if schedule == "COMPLETED" and execution in {"IN_PROGRESS", "NOT_STARTED"}:
        return Conflict(
            conflict_type="STATUS_CONFLICT",
            message=(
                f"Schedule says COMPLETED but execution says {execution}."
            ),
            severity="HIGH",
        )

    return None