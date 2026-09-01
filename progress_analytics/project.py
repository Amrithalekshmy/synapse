from dataclasses import dataclass
from typing import Iterable

from progress_analytics.activity import Activity
from progress_analytics.progress import calculate_progress
from progress_analytics.status import ActivityStatus


@dataclass
class ProjectSummary:
    total_activities: int
    completed_activities: int
    in_progress_activities: int
    delayed_activities: int
    overall_progress: float


def calculate_project_summary(
    activities: Iterable[Activity],
) -> ProjectSummary:
    """
    Aggregate activity-level progress into a project summary.
    """
    activities = list(activities)

    total = len(activities)

    completed = sum(
        1 for activity in activities
        if activity.status == ActivityStatus.COMPLETED
    )

    in_progress = sum(
        1 for activity in activities
        if activity.status == ActivityStatus.IN_PROGRESS
    )

    delayed = sum(
    1
    for activity in activities
    if activity.actual_finish is not None
    and activity.actual_finish > activity.planned_finish
    )

    if total == 0:
        overall_progress = 0.0
    else:
        overall_progress = (
            sum(calculate_progress(activity.status) for activity in activities)
            / total
        )

    return ProjectSummary(
        total_activities=total,
        completed_activities=completed,
        in_progress_activities=in_progress,
        delayed_activities=delayed,
        overall_progress=overall_progress,
    )