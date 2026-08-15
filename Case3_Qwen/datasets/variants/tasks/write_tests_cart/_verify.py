"""Verify that work/buggy.py matches pristine/good.py behavior."""


def main():
    import sys, os

    # Add the directory containing this file and its subdirectories to path.
    # This ensures we can import from both 'pristine' and 'work'.
    project_dir = os.path.dirname(os.path.abspath(__file__))
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

    # Import both implementations (they're in separate directories under project_dir).
    # Use unique module names to avoid conflicts.
    def load(path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("mod", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    good_mod = load(os.path.join(project_dir, "pristine", "good.py"))
    buggy_mod = load(os.path.join(project_dir, "work", "buggy.py"))

    Cart_good = good_mod.Cart
    Cart_buggy = buggy_mod.Cart

    print("Testing Cart implementation...")
    print("=" * 60)

    # Test basic functionality
    print("\n1. Basic add and total:")
    gc = Cart_good()
    bc = Cart_buggy()

    gc.add("SKU1", 10.0)
    bc.add("SKU1", 10.0)
    assert gc.total() == bc.total(), f"Basic add failed: good={gc.total()}, buggy={bc.total()}"
    print(f"   ✓ Basic add works (total={gc.total()})")

    # Test SAVE10 promo code
    print("\n2. SAVE10 promo code:")
    gc = Cart_good()
    bc = Cart_buggy()

    gc.add("SKU1", 200.0)
    bc.add("SKU1", 200.0)

    good_save10 = round(gc.apply_promo("SAVE10"), 2)
    buggy_save10 = round(bc.apply_promo("SAVE10"), 2)

    expected_save10 = 200.0 * 0.9

    if good_save10 == expected_save10 and buggy_save10 != expected_save10:
        print(f"   ✓ SAVE10 correctly uses percentage discount")
        print(f"     Good: {good_save10} (correct)")
        print(f"     Buggy: {buggy_save10} (BUG - using flat deduction instead of percentage)")
    else:
        print("   ✗ FAIL: SAVE10 not correctly implemented!")


if __name__ == "__main__":
    main()
