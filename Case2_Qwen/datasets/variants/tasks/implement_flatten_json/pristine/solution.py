def flatten_json(data: dict, prefix: str = "") -> dict:
    """Flatten nested dicts into dotted keys. Lists and other values are
    kept as-is (recursion stops at non-dict values).

    Example: flatten_json({"a": {"b": 1}, "c": [1, 2]})
             == {"a.b": 1, "c": [1, 2]}
    """
    if data is None or not isinstance(data, dict):
        raise TypeError(
            f"Input must be a dictionary (or empty), got {type(data).__name__}"
        )

    result = {}
    for key, value in data.items():
        # Convert non-string keys to strings with error context
        try:
            new_key = f"{prefix}.{key}" if prefix else str(key)
        except (TypeError, AttributeError):
            raise TypeError(
                "All dictionary keys must be string or integer types"
            )

        if isinstance(value, dict):
            result.update(flatten_json(value, new_key))
        else:
            # Keep non-dict values as-is (lists, ints, strings, etc.)
            result[new_key] = value

    return result
