from progress_analytics.risk import RiskLevel, calculate_risk


def test_large_delay_is_high_risk():
    assert calculate_risk(10, 80) == RiskLevel.HIGH


def test_delay_with_low_progress_is_high_risk():
    assert calculate_risk(5, 30) == RiskLevel.HIGH


def test_small_delay_is_medium_risk():
    assert calculate_risk(2, 80) == RiskLevel.MEDIUM


def test_on_time_is_low_risk():
    assert calculate_risk(0, 60) == RiskLevel.LOW


def test_early_completion_is_low_risk():
    assert calculate_risk(-3, 100) == RiskLevel.LOW


def test_invalid_progress():
    try:
        calculate_risk(2, 120)
        assert False
    except ValueError:
        assert True