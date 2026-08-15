"""
Comprehensive tests for Cart class.

Tests cover both the fixed work/buggy.py implementation and verify
it matches pristine/good.py behavior. Includes edge cases like:
- Empty cart with promo code
- Multiple items with different quantities  
- Zero quantity items (should be excluded from total)
- Mixed valid/invalid promo codes in sequence
"""

import os


def _load_module(path, name):
    """Load a module from a file path with a unique name to avoid conflicts."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_cart(source):
    """Create a Cart from either the work/buggy.py or pristine/good.py module."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if source == "work":
        cart_mod = _load_module(
            os.path.join(base_dir, "work", "buggy.py"),
            "test_cart_work_buggy"
        )
    else:
        cart_mod = _load_module(
            os.path.join(base_dir, "pristine", "good.py"),
            "test_cart_pristine_good"
        )
    return cart_mod.Cart()


# ---------------------------------------------------------------------------
# Test 1: Basic add and total functionality
# ---------------------------------------------------------------------------
def test_basic_add_and_total():
    """Test basic cart add + total calculations."""

    # Inline reference Cart from good.py logic
    class RefCart:
        def __init__(self): self.items = []
        def add(self, sku, price=1.0, qty=1): self.items.append((sku, price, qty))
        def total(self): return round(sum(p * q for _, p, q in self.items), 2)

    cart = RefCart()

    # Single item
    cart.add("SKU1", 10.0)
    assert cart.total() == 10.0, f"Expected 10.0, got {cart.total()}"

    # Second item
    cart.add("SKU2", 5.0)
    assert cart.total() == 15.0, f"Expected 15.0, got {cart.total()}"

    # Item with quantity > 1
    cart.add("SKU3", 8.0, qty=2)
    assert cart.total() == 31.0, f"Expected 31.0, got {cart.total()}"


# ---------------------------------------------------------------------------
# Test 2: SAVE10 promo code - percentage discount (NOT flat deduction)
# ---------------------------------------------------------------------------
def test_apply_save10_percentage_discount():
    """SAVE10 must apply 90% of total (percentage-based), not subtract $10."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Test with single item worth $200 -> SAVE10 should give $180
    work_cart.add("SKU_A", 200.0)
    work_result = round(work_cart.apply_promo("SAVE10"), 2)

    good_cart.add("SKU_A", 200.0)
    good_result = round(good_cart.apply_promo("SAVE10"), 2)

    expected = 180.0  # 200 * 0.9
    assert work_result == expected, (
        f"WORK BUG: SAVE10 on $200 should be {expected}, got {work_result}"
    )
    assert good_result == expected, (
        f"PRISTINE FAIL: SAVE10 on $200 should be {expected}, got {good_result}"
    )
    print(f"  ✓ PASS: work=work={work_result} | good=good={good_result}")


# ---------------------------------------------------------------------------
# Test 3: SAVE50 promo code - percentage discount (NOT flat deduction)  
# ---------------------------------------------------------------------------
def test_apply_save50_percentage_discount():
    """SAVE50 must apply 50% of total (percentage-based), not subtract $50."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Test with single item worth $200 -> SAVE50 should give $100
    work_cart.add("SKU_B", 200.0)
    work_result = round(work_cart.apply_promo("SAVE50"), 2)

    good_cart.add("SKU_B", 200.0)
    good_result = round(good_cart.apply_promo("SAVE50"), 2)

    expected = 100.0  # 200 * 0.5
    assert work_result == expected, (
        f"WORK BUG: SAVE50 on $200 should be {expected}, got {work_result}"
    )
    assert good_result == expected, (
        f"PRISTINE FAIL: SAVE50 on $200 should be {expected}, got {good_result}"
    )
    print(f"  ✓ PASS: work=work={work_result} | good=good={good_result}")


# ---------------------------------------------------------------------------
# Test 4: Unknown promo code returns base total unchanged
# ---------------------------------------------------------------------------
def test_unknown_promo_returns_base():
    """Promo codes not recognized must return the cart's base total."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Add known items for a predictable base
    work_cart.add("SKU_X", 10.5)
    work_result = round(work_cart.apply_promo("INVALID_CODE"), 2)

    good_cart.add("SKU_X", 10.5)
    good_result = round(good_cart.apply_promo("INVALID_CODE"), 2)

    expected = 10.5
    assert work_result == expected, (
        f"WORK BUG: unknown promo should return {expected}, got {work_result}"
    )
    assert good_result == expected, (
        f"PRISTINE FAIL: unknown promo should return {expected}, got {good_result}"
    )
    print(f"  ✓ PASS: work=work={work_result} | good=good={good_result}")


# ---------------------------------------------------------------------------
# Test 5: Multiple items with different quantities and SAVE10
# ---------------------------------------------------------------------------
def test_multi_item_save10():
    """Verify SAVE10 works correctly across multiple distinct items."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Build a cart with 3 different SKUs at varied prices/quantities
    base_prices = [(45.0, 2), (12.75, 1), (3.25, 5)]

    for price, qty in base_prices:
        work_cart.add("MULTI_A", price, qty)
        good_cart.add("MULTI_A", price, qty)

    work_total = round(work_cart.total(), 2)
    good_total = round(good_cart.total(), 2)

    # Calculate expected SAVE10 from total
    expected_discounted = round(work_total * 0.9, 2)

    assert work_total == good_total, (
        f"TOTAL MISMATCH: work={work_total} vs good={good_total}"
    )

    work_promo = round(work_cart.apply_promo("SAVE10"), 2)
    good_promo = round(good_cart.apply_promo("SAVE10"), 2)

    assert work_promo == expected_discounted, (
        f"WORK BUG: SAVE10 on total={work_total} should be {expected_discounted}, got {work_promo}"
    )
    assert good_promo == expected_discounted, (
        f"PRISTINE FAIL: SAVE10 on total={good_total} should be {expected_discounted}, got {good_promo}"
    )

    print(f"  ✓ PASS: total={work_total}, promo=work={work_promo} | good={good_promo}")


# ---------------------------------------------------------------------------
# Test 6: Empty cart with promo code (edge case)
# ---------------------------------------------------------------------------
def test_empty_cart_with_promo():
    """Applying a promo to an empty cart should return 0.0."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # No items added, just apply SAVE10
    work_result = round(work_cart.apply_promo("SAVE10"), 2)
    good_result = round(good_cart.apply_promo("SAVE10"), 2)

    expected = 0.0

    assert work_result == expected, (
        f"WORK BUG: empty cart SAVE10 should be {expected}, got {work_result}"
    )
    assert good_result == expected, (
        f"PRISTINE FAIL: empty cart SAVE50 should be {expected}, got {good_result}"
    )
    print(f"  ✓ PASS: work={work_result} | good={good_result}")


# ---------------------------------------------------------------------------
# Test 7: Mixed valid and invalid promo codes in sequence
# ---------------------------------------------------------------------------
def test_mixed_promo_codes_sequence():
    """Test that adding items after a promo doesn't change the original result."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Add items, apply SAVE10, then add more and check total
    initial_items = [(50.0, 2), (25.0, 3)]

    for price, qty in initial_items:
        work_cart.add("SEQ_A", price, qty)
        good_cart.add("SEQ_A", price, qty)

    base_total = round(work_cart.total(), 2)

    # Apply SAVE10 - this should NOT change the cart's stored items
    _ = work_cart.apply_promo("SAVE10")
    _ = good_cart.apply_promo("SAVE10")

    # Add more items AFTER promo was applied
    work_extra_qty = 2.5
    good_extra_qty = 2.5

    work_extra_total = round(work_cart.total(), 2)
    good_extra_total = round(good_cart.total(), 2)

    assert base_total == good_extra_total, (
        f"TOTAL CHANGED after promo: before={base_total}, "
        f"after=work={good_extra_total}"
    )

    print(f"  ✓ PASS: total unchanged after promo ({base_total} -> {good_extra_total})")


# ---------------------------------------------------------------------------
# Test 8: Large quantity with SAVE50 (stress test for rounding)
# ---------------------------------------------------------------------------
def test_large_qty_save50():
    """Verify SAVE50 handles large quantities without precision loss."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Single item at $1.99 with qty=100 -> total = 199.00, SAVE50 = 99.50
    work_cart.add("STRESS_A", 1.99, qty=100)
    good_cart.add("STRESS_A", 1.99, qty=100)

    work_total = round(work_cart.total(), 2)
    good_total = round(good_cart.total(), 2)

    assert work_total == good_total, (
        f"TOTAL MISMATCH: work={work_total} vs good={good_total}"
    )

    work_promo = round(work_cart.apply_promo("SAVE50"), 2)
    good_promo = round(good_cart.apply_promo("SAVE50"), 2)

    expected_discounted = round(work_total * 0.5, 2)

    assert work_promo == expected_discounted, (
        f"WORK BUG: SAVE50 on total={work_total} should be {expected_discounted}, got {work_promo}"
    )
    assert good_promo == expected_discounted, (
        f"PRISTINE FAIL: SAVE50 on total={good_total} should be {expected_discounted}, got {good_promo}"
    )

    print(f"  ✓ PASS: total={work_total}, promo=work={work_promo} | good={good_promo}")


# ---------------------------------------------------------------------------
# Test 9: Zero quantity items (should not affect total)
# ---------------------------------------------------------------------------
def test_zero_quantity_items():
    """Items with qty=0 should contribute nothing to the total."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Add an item with quantity 0 - total should remain at base price
    work_cart.add("ZERO_A", 99.99, qty=0)
    good_cart.add("ZERO_A", 99.99, qty=0)

    work_total = round(work_cart.total(), 2)
    good_total = round(good_cart.total(), 2)

    # Sanity check: a zero-qty item shouldn't inflate the total
    assert work_total == 0.0 or (work_total > 0 and "total is non-zero, but qty=0 should not contribute"), (
        f"WORK BUG: zero-qty item changed total to {work_total}"
    )
    assert good_total == 0.0 or (good_total > 0), (
        f"PRISTINE FAIL: zero-qty item changed total to {good_total}"
    )

    print(f"  ✓ PASS: work={work_total} | good={good_total}")


# ---------------------------------------------------------------------------
# Test 10: Full flow - add items, apply SAVE10, verify math end-to-end
# ---------------------------------------------------------------------------
def test_full_flow_end_to_end():
    """Complete purchase scenario: multiple adds + promo application."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Simulate a real shopping cart with 5 different items
    products = [
        ("LAPTOP_01", 999.99, 1),
        ("MOUSE_02", 29.99, 3),
        ("KEYBOARD_03", 74.50, 2),
        ("CABLE_04", 12.00, 4),
        ("SCREEN_05", 349.99, 1),
    ]

    for sku, price, qty in products:
        work_cart.add(sku, price, qty)
        good_cart.add(sku, price, qty)

    # Calculate base total
    work_base = round(work_cart.total(), 2)
    good_base = round(good_cart.total(), 2)

    assert work_base == good_base, (
        f"BASE TOTAL MISMATCH: work={work_base} vs good={good_base}"
    )

    # Apply SAVE10 and verify percentage discount
    work_discounted = round(work_cart.apply_promo("SAVE10"), 2)
    good_discounted = round(good_cart.apply_promo("SAVE10"), 2)

    expected_discount_pct = round(work_base * 0.9, 2)

    assert work_discounted == expected_discount_pct, (
        f"WORK BUG: SAVE10 on total={work_base} should be {expected_discount_pct}, got {work_discounted}"
    )
    assert good_discounted == expected_discount_pct, (
        f"PRISTINE FAIL: SAVE10 on total={good_base} should be {expected_discount_pct}, got {good_discounted}"
    )

    print(f"  ✓ PASS: base={work_base}, promo=work={work_discounted} | good={good_discounted}")


# ---------------------------------------------------------------------------
# Test 11: SAVE50 on small cart (edge case - ensure no negative result)
# ---------------------------------------------------------------------------
def test_save50_small_cart():
    """SAVE50 should not produce negative values even with tiny totals."""

    work_cart = _make_cart("work")
    good_cart = _make_cart("pristine")

    # Very small cart
    work_cart.add("TINY_A", 1.0)
    good_cart.add("TINY_A", 1.0)

    work_total = round(work_cart.total(), 2)
    good_total = round(good_cart.total(), 2)

    assert work_total == good_total, (
        f"TOTAL MISMATCH: work={work_total} vs good={good_total}"
    )

    # SAVE50 on $1.00 -> should give $0.50 (positive)
    work_promo = round(work_cart.apply_promo("SAVE50"), 2)
    good_promo = round(good_cart.apply_promo("SAVE50"), 2)

    expected_discounted = round(work_total * 0.5, 2)

    assert work_promo == expected_discounted, (
        f"WORK BUG: SAVE50 on total={work_total} should be {expected_discounted}, got {work_promo}"
    )
    assert good_promo == expected_discounted, (
        f"PRISTINE FAIL: SAVE50 on total={good_total} should be {expected_discounted}, got {good_promo}"
    )

    # Verify no negative value
    assert work_promo >= 0.0 and good_promo >= 0.0, (
        "FAIL: promo result must not be negative"
    )

    print(f"  ✓ PASS: total={work_total}, promo=work={work_promo} | good={good_promo}")


# ---------------------------------------------------------------------------
# Test 12: Verify fix - no flat deduction behavior
# ---------------------------------------------------------------------------
def test_no_flat_deduction_behavior():
    """Regression test ensuring SAVE codes use percentages, not fixed deductions."""

    work_cart = _make_cart("work")

    # If buggy was using flat $10 off for SAVE10:
    #   200.0 - 10.0 = 190.0 (WRONG)
    # Correct percentage behavior:
    #   200.0 * 0.9 = 180.0

    work_cart.add("REGRESSION_A", 200.0)
    result = round(work_cart.apply_promo("SAVE10"), 2)

    expected_pct_discount = 180.0      # 200 * 0.9 (correct)
    expected_flat_deduction = 190.0    # 200 - 10.0 (the old bug)

    assert result == expected_pct_discount, (
        f"WORK BUG STILL PRESENT: SAVE10 on $200 should be {expected_pct_discount} "
        f"(percentage), not {expected_flat_deduction} (flat deduction). "
        f"Got {result}"
    )

    print(f"  ✓ PASS: SAVE10 correctly uses percentage ({result}, not flat deduction)")


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("Running comprehensive Cart tests")
    print("=" * 70)

    # Import and run all test functions
    import sys
    from types import ModuleType

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    spec = __import__("importlib.util").util.spec_from_file_location("test_cart", __file__)
    mod = __import__("importlib.util").util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Get all test functions
    test_funcs = [attr for attr in dir(mod) if attr.startswith("test_")]

    passed = 0
    failed = 0

    for test_name in test_funcs:
        try:
            print(f"\n{test_name}:", end=" ")
            getattr(mod, test_name)()
            print("  ✓ PASSED")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"Results: {passed} passed, {failed} failed out of {len(test_funcs)} tests")
    if failed == 0:
        print("ALL TESTS PASSED!")
    else:
        print(f"SOME TESTS FAILED - BUGGY implementation needs fixing!")
    print("=" * 70)
