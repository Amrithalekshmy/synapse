import pytest

from progress_analytics.confidence import (
    ReviewDecision,
    get_review_decision,
)


def test_high_confidence_is_auto():
    assert get_review_decision(0.91) == ReviewDecision.AUTO


def test_boundary_auto():
    assert get_review_decision(0.85) == ReviewDecision.AUTO


def test_medium_confidence_requires_review():
    assert get_review_decision(0.72) == ReviewDecision.REVIEW


def test_boundary_review():
    assert get_review_decision(0.65) == ReviewDecision.REVIEW


def test_low_confidence_is_rejected():
    assert get_review_decision(0.40) == ReviewDecision.REJECT


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_invalid_confidence(confidence):
    with pytest.raises(ValueError):
        get_review_decision(confidence)