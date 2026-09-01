from datetime import date

from progress_analytics.activity import Activity
from progress_analytics.project import calculate_project_summary
from progress_analytics.status import ActivityStatus


def make_activity(activity_id, status):
    return Activity(
        activity_id=activity_id,
        planned_start=date(2026, 8, 1),
        planned_finish=date(2026, 8, 10),
        status=status,
    )


def test_project_summary():
    activities = [
        make_activity("A-1", ActivityStatus.COMPLETED),
        make_activity("A-2", ActivityStatus.COMPLETED),
        make_activity("A-3", ActivityStatus.IN_PROGRESS),
        make_activity("A-4", ActivityStatus.IN_PROGRESS),
        make_activity("A-5", ActivityStatus.NOT_STARTED),
    ]

    summary = calculate_project_summary(activities)

    assert summary.total_activities == 5
    assert summary.completed_activities == 2
    assert summary.in_progress_activities == 2
    assert summary.delayed_activities == 0
    assert summary.overall_progress == 0.6


def test_delayed_activities_are_counted():
    delayed_activity = Activity(
        activity_id="A-1",
        planned_start=date(2026, 8, 1),
        planned_finish=date(2026, 8, 10),
        actual_finish=date(2026, 8, 15),
        status=ActivityStatus.IN_PROGRESS,
    )

    completed_activity = make_activity(
        "A-2",
        ActivityStatus.COMPLETED,
    )

    summary = calculate_project_summary(
        [delayed_activity, completed_activity]
    )

    assert summary.total_activities == 2
    assert summary.delayed_activities == 1


def test_empty_project():
    summary = calculate_project_summary([])

    assert summary.total_activities == 0
    assert summary.overall_progress == 0.0