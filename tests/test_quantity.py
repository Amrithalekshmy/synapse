import pytest

from progress_analytics.quantity import calculate_quantity_progress


def test_partial_progress():
    assert calculate_quantity_progress(100, 60) == 60.0


def test_full_progress():
    assert calculate_quantity_progress(100, 100) == 100.0


def test_progress_cannot_exceed_100():
    assert calculate_quantity_progress(100, 120) == 100.0


def test_zero_planned_quantity_is_invalid():
    with pytest.raises(ValueError):
        calculate_quantity_progress(0, 50)


def test_negative_actual_quantity_is_invalid():
    with pytest.raises(ValueError):
        calculate_quantity_progress(100, -10)