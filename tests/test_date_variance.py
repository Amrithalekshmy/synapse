from datetime import date

from progress_analytics.date_variance import calculate_variance


def test_late_activity():
    planned = date(2026, 8, 20)
    actual = date(2026, 8, 24)

    assert calculate_variance(planned, actual) == 4


def test_early_activity():
    planned = date(2026, 8, 20)
    actual = date(2026, 8, 18)

    assert calculate_variance(planned, actual) == -2


def test_on_time_activity():
    planned = date(2026, 8, 20)
    actual = date(2026, 8, 20)

    assert calculate_variance(planned, actual) == 0