from datetime import date


def calculate_variance(planned: date, actual: date) -> int:
    """
    Calculate variance between planned and actual dates.

    Positive value = actual is later than planned.
    Negative value = actual is earlier than planned.
    Zero = exactly on schedule.
    """
    return (actual - planned).days
