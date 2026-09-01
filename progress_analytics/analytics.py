from progress_analytics.activity import Activity
from progress_analytics.date_variance import calculate_variance


def calculate_finish_variance(activity: Activity) -> int | None:
    """
    Calculate how many days early or late an activity finished.

    Positive  → finished late
    Negative  → finished early
    Zero      → finished on time
    None      → activity has not finished yet
    """
    if activity.actual_finish is None:
        return None

    return calculate_variance(
        activity.planned_finish,
        activity.actual_finish,
    )