from progress_analytics.status import ActivityStatus, can_transition


def test_not_started_can_start():
    assert can_transition(
        ActivityStatus.NOT_STARTED,
        ActivityStatus.IN_PROGRESS,
    ) is True


def test_in_progress_can_complete():
    assert can_transition(
        ActivityStatus.IN_PROGRESS,
        ActivityStatus.COMPLETED,
    ) is True


def test_completed_cannot_go_back():
    assert can_transition(
        ActivityStatus.COMPLETED,
        ActivityStatus.IN_PROGRESS,
    ) is False


def test_in_progress_can_pause():
    assert can_transition(
        ActivityStatus.IN_PROGRESS,
        ActivityStatus.ON_HOLD,
    ) is True