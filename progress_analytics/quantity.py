def calculate_quantity_progress(
    planned_quantity: float,
    actual_quantity: float,
) -> float:
    """
    Calculate completion percentage from planned and actual quantity.

    Example:
        planned = 100
        actual = 60
        result = 60.0
    """
    if planned_quantity <= 0:
        raise ValueError("Planned quantity must be greater than zero.")

    if actual_quantity < 0:
        raise ValueError("Actual quantity cannot be negative.")

    progress = (actual_quantity / planned_quantity) * 100

    return min(progress, 100.0)