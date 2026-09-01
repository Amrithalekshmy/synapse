from datetime import date

from progress_analytics.activity import Activity
from progress_analytics.analytics import calculate_finish_variance
from progress_analytics.status import ActivityStatus


def test_activity_finished_late():
    activity = Activity(
        activity_id="A-101",
        planned_start=date(2026, 8, 15),
        planned_finish=date(2026, 8, 20),
        actual_finish=date(2026, 8, 24),
        status=ActivityStatus.COMPLETED,
    )

    assert calculate_finish_variance(activity) == 4


def test_activity_finished_early():
    activity = Activity(
        activity_id="A-102",
        planned_start=date(2026, 8, 15),
        planned_finish=date(2026, 8, 20),
        actual_finish=date(2026, 8, 18),
        status=ActivityStatus.COMPLETED,
    )

    assert calculate_finish_variance(activity) == -2


def test_unfinished_activity_has_no_finish_variance():
    activity = Activity(
        activity_id="A-103",
        planned_start=date(2026, 8, 15),
        planned_finish=date(2026, 8, 20),
        status=ActivityStatus.IN_PROGRESS,
    )

    assert calculate_finish_variance(activity) is None