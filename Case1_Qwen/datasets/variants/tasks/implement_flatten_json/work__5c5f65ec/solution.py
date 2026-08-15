#!/usr/bin/env python3
"""Recursive JSON flattener: nested dicts into dot-separated key paths.

Usage (file input):
    python solution.py <input.json>

Usage (stdin):
    echo '{"a":{"b":1},"c":[1,2]}' | python solution.py -

Examples:
    flatten_json({"a": {"b": 1}, "c": [1, 2]}) == {"a.b": 1, "c": [1, 2]}
    flatten_json({"x": 42})                      == {"x": 42}
    flatten_json({})                             == {}
"""

import json
import sys


def flatten_json(data: dict, prefix: str = "") -> dict:
    """Flatten nested dicts into dot-separated keys.

    Lists and other non-dict values are kept as-is (recursion stops at them).
    Non-string leaf values remain their original type; only non-string keys
    are converted to strings for path construction.

    Args:
        data: The dictionary to flatten. Must be a dict (or empty).
        prefix: Current key path prefix (used internally, not exposed).

    Returns:
        A flat dict with dot-separated keys and original leaf values.

    Raises:
        TypeError: If input is None or not a dict.
        ValueError: If JSON parsing fails for non-dict inputs in CLI mode.
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


def main():
    """CLI entry point. Reads JSON from file argument or stdin, flattens, and outputs."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Flatten nested JSON dictionaries into dot-separated keys.",
        epilog=(
            "Examples:\n"
            "  python solution.py input.json\n"
            "  echo '{\"a\":{\"b\":1}}' | python solution.py -\n"
            "  cat data.json | python solution.py -"
        ),
    )
    parser.add_argument(
        "input",
        help="Path to JSON file, or '-' for stdin input",
    )

    args = parser.parse_args()

    # Read raw text from file or stdin
    if args.input == "-":
        try:
            raw_data = sys.stdin.read()
        except KeyboardInterrupt:
            print("Error: Standard input interrupted.", file=sys.stderr)
            sys.exit(130)
        if not raw_data.strip():
            print("Error: Empty input provided via stdin.", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                raw_data = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        except PermissionError:
            print(f"Error: Permission denied reading: {args.input}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file '{args.input}': {e}", file=sys.stderr)
            sys.exit(1)

    # Parse JSON and validate structure
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input - {e.msg}: line {e.lineno}, column {e.colno}", file=sys.stderr)
        sys.exit(2)

    if not isinstance(data, dict):
        print("Error: Input must be a JSON object (dict).", file=sys.stderr)
        sys.exit(3)

    # Flatten the nested structure
    result = flatten_json(data)

    # Output as formatted JSON to stdout
    try:
        output_str = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        print(output_str, end="")
    except (TypeError, ValueError) as e:
        print(f"Error serializing result: {e}", file=sys.stderr)
        sys.exit(4)


if __name__ == "__main__":
    main()
