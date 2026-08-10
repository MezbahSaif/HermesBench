# Unit tests for Thermometer module
# Tests must pass against good.py and fail against buggy.py

from good import Thermometer  # Import correct module - tests will fail if we import buggy instead


def test_average_single_reading():
    """Test average with a single reading."""
    t = Thermometer()
    t.record(25.0)
    avg = t.average()
    assert avg == 25.0, f"Expected 25.0, got {avg}"


def test_average_two_same_readings():
    """Test average with two identical readings."""
    t = good.Thermometer()
    t.record(10.0)
    t.record(10.0)
    avg = t.average()
    assert avg == 10.0, f"Expected 10.0, got {avg}"


def test_average_two_different_readings():
    """Test average with two different readings."""
    t = good.Thermometer()
    t.record(20.0)
    t.record(30.0)
    avg = t.average()
    assert avg == 25.0, f"Expected 25.0, got {avg}"


def test_average_rounds_up():
    """Test that average properly rounds up (catches truncation bug)."""
    t = good.Thermometer()
    # 3 values: 10, 10, 11 -> sum=31, avg=10.333... should round to 10.33
    t.record(10.0)
    t.record(10.0)
    t.record(11.0)
    avg = t.average()
    # int(10.333...) would truncate to 10, but round gives 10.33
    assert abs(avg - 10.33) < 0.01, f"Expected ~10.33 (rounded), got {avg} (truncated?)"


def test_average_rounds_down():
    """Test that average properly rounds down."""
    t = good.Thermometer()
    # 2 values: 10 and 11 -> sum=21, avg=10.5 should round to 10.5 (banker's rounding)
    t.record(10.0)
    t.record(11.0)
    avg = t.average()
    assert abs(avg - 10.5) < 0.01, f"Expected ~10.5, got {avg}"


def test_average_non_integer_result():
    """Test average where result has decimal places."""
    t = good.Thermometer()
    # 3 values: 10, 20, 21 -> sum=51, avg=17.0 (exact)
    t.record(10.0)
    t.record(20.0)
    t.record(21.0)
    avg = t.average()
    assert avg == 17.0, f"Expected 17.0, got {avg}"


def test_average_decimal_input():
    """Test average with decimal (non-integer) input values."""
    t = good.Thermometer()
    # Values that produce a repeating decimal: 1, 2, 4 -> sum=7, avg=2.333...
    t.record(1.0)
    t.record(2.0)
    t.record(4.0)
    avg = t.average()
    # int(2.333...) = 2 (bug), round(2.333..., 2) = 2.33 (correct)
    assert abs(avg - 2.33) < 0.01, f"Expected ~2.33 (rounded), got {avg} (truncated?)"


def test_average_many_values():
    """Test average with many values to catch precision issues."""
    t = good.Thermometer()
    # Generate values that average to something needing rounding
    for i in range(100):
        t.record(i)
    avg = t.average()
    # Expected: sum(0-99)/100 = 4950/100 = 49.5
    expected = 49.5
    assert abs(avg - expected) < 0.01, f"Expected ~{expected}, got {avg}"


def test_average_raises_error_no_readings():
    """Test that average raises ValueError when no readings exist."""
    t = good.Thermometer()
    try:
        t.average()
        assert False, "Expected ValueError to be raised"
    except ValueError as e:
        assert str(e) == "no readings", f"Expected 'no readings', got '{e}'"


def test_average_small_values():
    """Test average with small values."""
    t = good.Thermometer()
    # Values 0.1, 0.2 -> sum=0.3, avg=0.15
    t.record(0.1)
    t.record(0.2)
    avg = t.average()
    assert abs(avg - 0.15) < 0.01, f"Expected ~0.15, got {avg}"


def test_average_large_values():
    """Test average with large values."""
    t = good.Thermometer()
    # Values 1000, 2000 -> sum=3000, avg=1500.0
    t.record(1000.0)
    t.record(2000.0)
    avg = t.average()
    assert avg == 1500.0, f"Expected 1500.0, got {avg}"


def test_average_extreme_truncation_case():
    """Test case that would clearly expose truncation bug."""
    t = good.Thermometer()
    # Three values: 2, 3, 4 -> sum=9, avg=3.0 (exact)
    t.record(2.0)
    t.record(3.0)
    t.record(4.0)
    avg = t.average()
    assert avg == 3.0, f"Expected 3.0, got {avg}"


if __name__ == "__main__":
    # Run all tests
    import sys
    
    test_funcs = [func for name, func in globals().items() if name.startswith('test_')]
    
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"PASS: {func.__name__}")
        except AssertionError as e:
            print(f"FAIL: {func.__name__}: {e}")
            failed += 1
    
    if failed > 0:
        sys.exit(1)
