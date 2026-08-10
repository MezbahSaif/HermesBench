# Test suite for good.py - all tests should pass against good module
import good


def test_median_empty_list():
    """Test that median raises ValueError on empty input."""
    try:
        good.median([])
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "empty list"


def test_median_single_element():
    """Test median of a single element list."""
    values = [5]
    result = good.median(values)
    assert result == 5.0


def test_median_odd_count():
    """Test median with odd number of elements."""
    values = [1, 3, 5, 7, 9]
    result = good.median(values)
    assert result == 5.0


def test_median_even_count():
    """Test median with even number of elements."""
    values = [1, 2, 3, 4]
    result = good.median(values)
    # Median of [1,2,3,4] is (2+3)/2 = 2.5
    assert result == 2.5


def test_median_unsorted_input():
    """Test median with unsorted input list."""
    values = [5, 1, 9, 3, 7]
    result = good.median(values)
    assert result == 5.0


def test_median_duplicate_values():
    """Test median with duplicate values."""
    values = [2, 2, 3, 3]
    result = good.median(values)
    # Median of [2,2,3,3] is (2+3)/2 = 2.5
    assert result == 2.5


def test_median_negative_values():
    """Test median with negative values."""
    values = [-5, -2, -10, -1]
    result = good.median(values)
    # Sorted: [-10, -5, -2, -1], median = (-5 + -2)/2 = -3.5
    assert result == -3.5


def test_median_mixed_positive_negative():
    """Test median with mixed positive and negative values."""
    values = [-10, 0, 10]
    result = good.median(values)
    assert result == 0


def test_median_float_values():
    """Test median with float values."""
    values = [1.5, 2.5, 3.5]
    result = good.median(values)
    assert result == 2.5


def test_mean_empty_list():
    """Test that mean raises ValueError on empty input."""
    try:
        good.mean([])
        assert False, "Expected ValueError"
    except ValueError as e:
        assert str(e) == "empty list"


def test_mean_single_element():
    """Test mean of a single element."""
    values = [10]
    result = good.mean(values)
    assert result == 10.0


def test_mean_two_elements():
    """Test mean with two elements."""
    values = [3, 7]
    result = good.mean(values)
    assert result == 5.0


def test_mean_odd_count():
    """Test mean with odd number of elements."""
    values = [1, 2, 3, 4, 5]
    result = good.mean(values)
    assert result == 3.0


def test_mean_even_count():
    """Test mean with even number of elements."""
    values = [2, 4, 6, 8]
    result = good.mean(values)
    # (2+4+6+8)/4 = 5
    assert result == 5.0


def test_mean_unsorted_input():
    """Test mean with unsorted input."""
    values = [10, 1, 3, 2]
    result = good.mean(values)
    # (10+1+3+2)/4 = 4.0
    assert result == 4.0


def test_mean_negative_values():
    """Test mean with negative values."""
    values = [-5, -3, -1]
    result = good.mean(values)
    # (-5-3-1)/3 = -3
    assert result == -3.0


def test_mean_float_values():
    """Test mean with float values."""
    values = [1.0, 2.0, 3.0]
    result = good.mean(values)
    # (1+2+3)/3 = 2.0
    assert result == 2.0


def test_mean_mixed_values():
    """Test mean with mixed positive and negative values."""
    values = [-5, 5, -5, 5]
    result = good.mean(values)
    # (-5+5-5+5)/4 = 0
    assert result == 0.0


def test_median_does_not_mutate_input():
    """CRITICAL: Test that median does not mutate the input list."""
    original = [3, 1, 4, 1, 5]
    original_copy = original.copy()
    
    result = good.median(original)
    
    # Verify result is correct
    assert result == 3.0
    
    # Verify input was NOT mutated (this will FAIL against buggy.py!)
    assert original == original_copy, "median() mutated the input list!"


def test_mean_does_not_mutate_input():
    """Test that mean does not mutate the input list."""
    values = [1, 2, 3]
    original_copy = values.copy()
    
    result = good.mean(values)
    
    # Verify mean is correct
    assert result == 2.0
    
    # Verify input was NOT mutated
    assert values == original_copy, "mean() mutated the input list!"


def test_median_preserves_original_order():
    """Test that median preserves original order (not just content)."""
    values = [5, 1, 4, 2]
    
    # Store the exact state before calling
    state_before = tuple(values)
    
    result = good.median(values)
    
    assert result == 2.5
    
    # Verify order is preserved (not mutated in place)
    state_after = tuple(values)
    assert state_before == state_after, "Input list order was modified!"


def test_median_large_list():
    """Test median with a larger list."""
    values = list(range(1, 21))
    result = good.median(values)
    # Sorted [1..20], mid positions are 9 and 10 -> (9+10)/2 = 9.5
    assert result == 9.5
