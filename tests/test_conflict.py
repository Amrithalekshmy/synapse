from datetime import date

from progress_analytics.conflict import (
    detect_date_conflict,
    detect_status_conflict,
)


def test_no_date_conflict_when_on_time():
    result = detect_date_conflict(
        date(2026, 8, 20),
        date(2026, 8, 20),
    )

    assert result is None


def test_date_delay_detected():
    result = detect_date_conflict(
        date(2026, 8, 20),
        date(2026, 8, 25),
    )

    assert result is not None
    assert result.conflict_type == "DATE_DELAY"
    assert result.severity == "MEDIUM"


def test_large_date_delay_is_high():
    result = detect_date_conflict(
        date(2026, 8, 20),
        date(2026, 8, 30),
    )

    assert result is not None
    assert result.severity == "HIGH"


def test_status_conflict_detected():
    result = detect_status_conflict(
        "COMPLETED",
        "IN_PROGRESS",
    )

    assert result is not None
    assert result.conflict_type == "STATUS_CONFLICT"
    assert result.severity == "HIGH"


def test_matching_status_has_no_conflict():
    result = detect_status_conflict(
        "IN_PROGRESS",
        "IN_PROGRESS",
    )

    assert result is None


def test_missing_dates_have_no_conflict():
    result = detect_date_conflict(None, date(2026, 8, 20))

    assert result is None