#!/usr/bin/env python3
"""Test suite for flatten_json."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solution import flatten_json


def test_basic_nesting():
    assert flatten_json({"a": {"b": 1}, "c": [1, 2]}) == {"a.b": 1, "c": [1, 2]}
    print("PASS: basic nesting")

def test_empty_dict():
    assert flatten_json({}) == {}
    print("PASS: empty dict")

def test_shallow_string():
    assert flatten_json({"x": "hello"}) == {"x": "hello"}
    print("PASS: shallow string value")

def test_deep_nesting():
    r = flatten_json({"a": {"b": {"c": {"d": 5}}}})
    assert r == {"a.b.c.d": 5}
    print("PASS: deep nesting")

def test_mixed_types():
    data = {"x": {"y": "hello"}, "z": [1,2], "w": 3}
    assert flatten_json(data) == {"x.y": "hello", "z": [1, 2], "w": 3}
    print("PASS: mixed types")

def test_sibling_keys():
    data = {"a": {"b": 1}, "a2": {"c": 2}}
    assert flatten_json(data) == {"a.b": 1, "a2.c": 2}
    print("PASS: sibling keys")

def test_list_input_raises():
    try:
        flatten_json([1, 2, 3])
        assert False
    except TypeError:
        pass
    print("PASS: list input raises TypeError")

def test_none_input_raises():
    try:
        flatten_json(None)
        assert False
    except TypeError:
        pass
    print("PASS: None input raises TypeError")

def test_numeric_key():
    r = flatten_json({1: {"a": 2}})
    assert r == {"1.a": 2}
    print("PASS: numeric key conversion")

def test_empty_nested_dict_ignored():
    """Empty dict nested inside another dict produces no entries (correct)."""
    r = flatten_json({"a": {}})
    assert r == {}
    print("PASS: empty nested dict yields nothing")

def test_list_of_dicts_preserved():
    data = {"items": [{"name": "x"}]}
    assert flatten_json(data) == {"items": [{"name": "x"}]}
    print("PASS: list of dicts preserved as-is")

def test_empty_dict_mid_level():
    r = flatten_json({"a": {"b": {}, "c": 3}})
    assert r == {"a.c": 3}
    print("PASS: empty dict mid-level ignored, sibling kept")


if __name__ == "__main__":
    tests = [k for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = []
    for t in sorted(tests):
        try:
            globals()[t]()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t}: {e}")
            failed.append(t)
    print()
    print(f"Results: {passed}/{len(tests)} passed")
    if failed:
        sys.exit(1)
