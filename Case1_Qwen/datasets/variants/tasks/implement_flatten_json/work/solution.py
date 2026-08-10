def flatten_json(data: dict, prefix: str = "") -> dict:
    """Flatten nested dicts into dotted keys. Lists and other values are
    kept as-is (recursion stops at non-dict values).

    Example: flatten_json({"a": {"b": 1}, "c": [1, 2]})
             == {"a.b": 1, "c": [1, 2]}
    """
    result = {}
    
    if not isinstance(data, dict):
        return data
    
    for key, value in data.items():
        # Build new key: skip dot when prefix is empty
        if prefix:
            new_key = f"{prefix}.{key}"
        else:
            new_key = key
        
        if isinstance(value, dict):
            # Recursively flatten nested dict
            # Pass new_key (without trailing dot) and the recursive call adds dots before children
            nested_result = flatten_json(value, new_key)
            result.update(nested_result)
        else:
            # Keep non-dict values as-is (including lists, None, etc.)
            result[new_key] = value
    
    return result
