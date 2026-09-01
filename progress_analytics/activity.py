from dataclasses import dataclass
from datetime import date

from progress_analytics.status import ActivityStatus


@dataclass
class Activity:
    activity_id: str
    planned_start: date
    planned_finish: date
    status: ActivityStatus
    actual_start: date | None = None
    actual_finish: date | None = None