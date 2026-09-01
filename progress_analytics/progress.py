from progress_analytics.status import ActivityStatus


def calculate_progress(status: ActivityStatus) -> float:
    """
    Calculate basic activity progress from its current status.

    Returns progress as a value between 0.0 and 1.0.
    """
    progress_by_status = {
        ActivityStatus.NOT_STARTED: 0.0,
        ActivityStatus.IN_PROGRESS: 0.5,
        ActivityStatus.ON_HOLD: 0.5,
        ActivityStatus.COMPLETED: 1.0,
        ActivityStatus.CANCELLED: 0.0,
    }

    return progress_by_status[status]