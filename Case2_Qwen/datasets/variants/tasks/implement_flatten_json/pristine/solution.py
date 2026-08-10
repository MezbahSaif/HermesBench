def flatten_json(data: dict, prefix: str = "") -> dict:
    """Flatten nested dicts into dotted keys. Lists and other values are
    kept as-is (recursion stops at non-dict values).

    Example: flatten_json({"a": {"b": 1}, "c": [1, 2]})
             == {"a.b": 1, "c": [1, 2]}
    """
    raise NotImplementedError
