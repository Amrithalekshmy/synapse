from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


def calculate_risk(
    variance_days: int,
    progress_percent: float,
) -> RiskLevel:
    """
    Calculate schedule risk using date variance and actual progress.

    High risk:
        Significant delay (> 7 days), or
        Moderate delay (> 3 days) with low progress.

    Medium risk:
        Smaller delay (> 0 days).

    Low risk:
        On time/early with reasonable progress.
    """
    if not 0.0 <= progress_percent <= 100.0:
        raise ValueError("Progress must be between 0 and 100.")

    if variance_days > 7:
        return RiskLevel.HIGH

    if variance_days > 3 and progress_percent < 50:
        return RiskLevel.HIGH

    if variance_days > 0:
        return RiskLevel.MEDIUM

    return RiskLevel.LOW