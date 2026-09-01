from progress_analytics.progress import calculate_progress
from progress_analytics.status import ActivityStatus


def test_not_started_is_zero():
    assert calculate_progress(ActivityStatus.NOT_STARTED) == 0.0


def test_in_progress_is_fifty_percent():
    assert calculate_progress(ActivityStatus.IN_PROGRESS) == 0.5


def test_on_hold_is_fifty_percent():
    assert calculate_progress(ActivityStatus.ON_HOLD) == 0.5


def test_completed_is_full_progress():
    assert calculate_progress(ActivityStatus.COMPLETED) == 1.0


def test_cancelled_is_zero():
    assert calculate_progress(ActivityStatus.CANCELLED) == 0.0