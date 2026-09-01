from enum import Enum


class ReviewDecision(str, Enum):
    AUTO = "auto"
    REVIEW = "review"
    REJECT = "reject"


def get_review_decision(confidence: float) -> ReviewDecision:
    """
    Decide whether a matched event can be accepted automatically,
    requires human review, or should be rejected.
    """
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0.0 and 1.0.")

    if confidence >= 0.85:
        return ReviewDecision.AUTO

    if confidence >= 0.65:
        return ReviewDecision.REVIEW

    return ReviewDecision.REJECT