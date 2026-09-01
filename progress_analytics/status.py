from enum import Enum


class ActivityStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ON_HOLD = "ON_HOLD"
    CANCELLED = "CANCELLED"
VALID_TRANSITIONS = {
    ActivityStatus.NOT_STARTED: {
        ActivityStatus.IN_PROGRESS,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.IN_PROGRESS: {
        ActivityStatus.COMPLETED,
        ActivityStatus.ON_HOLD,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.ON_HOLD: {
        ActivityStatus.IN_PROGRESS,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.COMPLETED: set(),
    ActivityStatus.CANCELLED: set(),
}


def can_transition(
    current: ActivityStatus,
    new: ActivityStatus,
) -> bool:
    """Return True when the requested status transition is allowed."""
    return new in VALID_TRANSITIONS[current]