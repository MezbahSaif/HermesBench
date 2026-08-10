"""Test runner to validate tests work against both modules."""
import sys
sys.path.insert(0, '.')

def run_test_suite(module_name):
    """Run all test functions against a specific module."""
    print("=" * 60)
    print(f"Running tests vs {module_name.upper()} module\n")
    
    passed = 0
    failed = []
    
    for func_name in ['test_median_empty_list', 'test_median_single_element', 
                      'test_median_odd_count', 'test_median_even_count',
                      'test_median_unsorted_input', 'test_median_duplicate_values',
                      'test_median_negative_values', 'test_median_mixed_positive_negative',
                      'test_median_float_values', 'test_mean_empty_list',
                      'test_mean_single_element', 'test_mean_two_elements',
                      'test_mean_odd_count', 'test_mean_even_count',
                      'test_mean_unsorted_input', 'test_mean_negative_values',
                      'test_mean_float_values', 'test_mean_mixed_values',
                      'test_median_does_not_mutate_input', 'test_mean_does_not_mutate_input',
                      'test_median_preserves_original_order', 'test_median_large_list']:
        
        func = globals()[func_name]
        try:
            # Temporarily replace the module reference in the namespace
            import good as _good
            import buggy as _buggy
            
            if module_name == "buggy":
                sys.modules['good'] = _buggy
            else:
                sys.modules['good'] = _good
            
            func()
            passed += 1
            print(f"  ✓ {func_name}")
        except AssertionError as e:
            failed.append((func_name, str(e)))
            print(f"  ✗ {func_name}: {e}")
    
    print("=" * 60)
    return module_name, passed, len(failed)

# Run tests against buggy module first
run_test_suite("buggy")

print("\n\nNow running against good module...\n")
run_test_suite("good")
