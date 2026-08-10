#!/usr/bin/env python
"""Test runner for Thermometer module tests."""

import sys
sys.path.insert(0, 'G:/HermesBench/datasets/variants/tasks/write_tests_temperature/work')


def test_with_module(module_name):
    """Run all tests against a given module."""
    print("=" * 60)
    print(f"TESTING AGAINST {module_name.upper()}.PY")
    print("=" * 60)
    
    # Clear globals
    globals().clear()
    
    # Import the module
    if module_name == "good":
        import good
        Thermometer = good.Thermometer
    elif module_name == "buggy":
        import buggy
        Thermometer = buggy.Thermometer
    
    # Define tests
    def test_average_single_reading():
        t = Thermometer()
        t.record(25.0)
        avg = t.average()
        assert avg == 25.0, f"Expected 25.0, got {avg}"

    def test_average_two_same_readings():
        t = Thermometer()
        t.record(10.0)
        t.record(10.0)
        avg = t.average()
        assert avg == 10.0, f"Expected 10.0, got {avg}"

    def test_average_two_different_readings():
        t = Thermometer()
        t.record(20.0)
        t.record(30.0)
        avg = t.average()
        assert avg == 25.0, f"Expected 25.0, got {avg}"

    def test_average_rounds_up():
        """Test that average properly rounds up (catches truncation bug)."""
        t = Thermometer()
        t.record(10.0)
        t.record(10.0)
        t.record(11.0)
        avg = t.average()
        assert abs(avg - 10.33) < 0.01, f"Expected ~10.33 (rounded), got {avg} (truncated?)"

    def test_average_rounds_down():
        """Test that average properly rounds down."""
        t = Thermometer()
        t.record(10.0)
        t.record(11.0)
        avg = t.average()
        assert abs(avg - 10.5) < 0.01, f"Expected ~10.5, got {avg}"

    def test_average_decimal_input():
        """Test average with decimal input values."""
        t = Thermometer()
        t.record(1.0)
        t.record(2.0)
        t.record(4.0)
        avg = t.average()
        assert abs(avg - 2.33) < 0.01, f"Expected ~2.33 (rounded), got {avg} (truncated?)"

    def test_average_many_values():
        """Test average with many values."""
        t = Thermometer()
        for i in range(100):
            t.record(i)
        avg = t.average()
        expected = 49.5
        assert abs(avg - expected) < 0.01, f"Expected ~{expected}, got {avg}"

    def test_average_raises_error_no_readings():
        """Test that average raises ValueError when no readings exist."""
        t = Thermometer()
        try:
            t.average()
            assert False, "Expected ValueError to be raised"
        except ValueError as e:
            assert str(e) == "no readings", f"Expected 'no readings', got '{e}'"

    def test_average_small_values():
        """Test average with small values."""
        t = Thermometer()
        t.record(0.1)
        t.record(0.2)
        avg = t.average()
        assert abs(avg - 0.15) < 0.01, f"Expected ~0.15, got {avg}"

    def test_average_large_values():
        """Test average with large values."""
        t = Thermometer()
        t.record(1000.0)
        t.record(2000.0)
        avg = t.average()
        assert avg == 1500.0, f"Expected 1500.0, got {avg}"

    def test_average_extreme_truncation_case():
        """Test case that would clearly expose truncation bug."""
        t = Thermometer()
        t.record(2.0)
        t.record(3.0)
        t.record(4.0)
        avg = t.average()
        assert avg == 3.0, f"Expected 3.0, got {avg}"

    # Run all tests
    test_funcs = [test_average_single_reading, test_average_two_same_readings,
                  test_average_two_different_readings, test_average_rounds_up,
                  test_average_rounds_down, test_average_decimal_input,
                  test_average_many_values, test_average_raises_error_no_readings,
                  test_average_small_values, test_average_large_values,
                  test_average_extreme_truncation_case]
    
    failed = 0
    for func in test_funcs:
        try:
            func()
            print(f"✓ PASS: {func.__name__}")
        except AssertionError as e:
            print(f"✗ FAIL: {func.__name__}: {e}")
            failed += 1
    
    passed = len(test_funcs) - failed
    print(f"\n{module_name}.py: {passed}/{len(test_funcs)} tests passed")
    return failed


if __name__ == "__main__":
    good_failed = test_with_module("good")
    buggy_failed = test_with_module("buggy")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Good.py (correct): {11 - good_failed} tests passed")
    print(f"Buggy.py (truncation bug): {11 - buggy_failed} tests passed")
    
    if good_failed == 0 and buggy_failed > 0:
        print("\n✓ SUCCESS: Tests correctly identify the truncation bug!")
        sys.exit(0)
    else:
        print("\n✗ FAILURE: Tests need adjustment.")
        sys.exit(1)
