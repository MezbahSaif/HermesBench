"""Merge overlapping intervals.

Merges all overlapping or touching intervals and returns them sorted by start value.
Touching intervals ([1,2] and [2,3]) are merged as well.

Usage:
    python solution.py file.json [--output output.json]
    echo '[{"start": 1, "end": 5}, {"start": 8, "end": 10}]' | python solution.py -
"""

import argparse
import json
import sys


def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    """Merge all overlapping intervals and return them sorted by start.

    Touching intervals ([1,2] and [2,3]) merge as well.

    Args:
        intervals: A list of [start, end] pairs (integers or floats).

    Returns:
        A list of merged non-overlapping intervals sorted by start value.

    Raises:
        TypeError: If intervals is not a list of lists/tuples.
        ValueError: If any interval has fewer than 2 elements.

    Examples:
        >>> merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
        [[1, 6], [8, 10], [15, 18]]
        >>> merge_intervals([])
        []
        >>> merge_intervals([[1, 4], [2, 6], [3, 8]])
        [[1, 8]]
    """
    if not isinstance(intervals, list):
        raise TypeError(
            f"Expected a list of intervals, got {type(intervals).__name__}"
        )

    empty = []
    if intervals is None or len(intervals) == 0:
        return empty

    # Validate each interval
    for i, iv in enumerate(intervals):
        if not isinstance(iv, (list, tuple)) or len(iv) != 2:
            raise ValueError(
                f"Interval at index {i} must be a list/tuple of two elements, "
                f"got {iv!r}"
            )

    # Sort by start value; break ties by end value (ascending)
    intervals.sort(key=lambda x: (x[0], x[1]))

    merged = [list(intervals[0])]
    for current_start, current_end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        # Merge if overlapping or touching (current_start <= prev_end)
        if current_start <= prev_end:
            merged[-1] = [prev_start, max(prev_end, current_end)]
        else:
            merged.append([current_start, current_end])

    return merged


def parse_intervals_from_json(data):
    """Parse intervals from a JSON-serializable data structure.

    Accepts a list of [start, end] pairs or an object with 'intervals' key.
    Supports nested structures like [{"intervals": [[1,2], [3,4]]}].

    Args:
        data: The parsed input data.

    Returns:
        A flat list of intervals.
    """
    # If it's a dict with an 'intervals' key, extract from there
    if isinstance(data, dict):
        if "intervals" in data and data["intervals"] is not None:
            return parse_intervals_from_json(data["intervals"])
        raise ValueError("Input dict must contain an 'intervals' key")

    # If it's a list of dicts with start/end keys, flatten first
    if isinstance(data, list):
        flat = []
        for item in data:
            if isinstance(item, dict) and "start" in item and "end" in item:
                flat.append([item["start"], item["end"]])
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                flat.append(list(item))
            else:
                raise ValueError(f"Unexpected data format: {item!r}")

        # Validate
        for i, iv in enumerate(flat):
            if not isinstance(iv[0], (int, float)):
                raise TypeError(
                    f"Interval at index {i} start value must be numeric, got {type(iv[0]).__name__}"
                )
            if not isinstance(iv[1], (int, float)):
                raise TypeError(
                    f"Interval at index {i} end value must be numeric, got {type(iv[1]).__name__}"
                )

        return flat

    # If it's a list of lists/tuples, validate and convert
    if isinstance(data, list):
        flat = []
        for i, item in enumerate(data):
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError(
                    f"Element at index {i} must be a pair [start, end], got {item!r}"
                )
            flat.append(list(item))
        return flat

    raise TypeError(f"Expected list of intervals, got {type(data).__name__}")


def main(argv=None):
    """CLI entry point.

    Reads interval data from a JSON file or stdin and prints merged intervals.

    Examples:
        python solution.py input.json
        echo '{"intervals": [[1,3],[2,6]]}' | python solution.py -
        python solution.py intervals.txt --output results.json
    """
    parser = argparse.ArgumentParser(
        prog="solution",
        description=(
            "Merge overlapping or touching intervals read from a JSON file or stdin. "
            "Outputs merged intervals as JSON."
        ),
        epilog=(
            'Examples:\n'
            '  python solution.py input.json\n'
            '  echo \'{"intervals": [[1,3],[2,6]]}\' | python solution.py -\n'
            '  python solution.py intervals.txt --output results.json'
        ),
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help=(
            "Path to a JSON file containing intervals, or '-' for stdin. "
            "The JSON may contain a top-level list of [start,end] pairs "
            "or an object with an 'intervals' key."
        ),
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: stdout)",
    )

    args = parser.parse_args(argv)

    # Read input
    if args.input == "-":
        raw_data = sys.stdin.read()
        if not raw_data.strip():
            print("Error: Empty stdin input.", file=sys.stderr)
            return 1
    else:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                raw_data = f.read()
        except FileNotFoundError:
            print(f"Error: File not found: {args.input}", file=sys.stderr)
            return 1
        except OSError as e:
            print(f"Error reading file {args.input}: {e}", file=sys.stderr)
            return 1

    # Parse JSON
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON input: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        raw_input = args.input if args.input != "-" else "<stdin>"
        print(
            f"Error: Input must be a JSON object with an 'intervals' key. "
            f"(Read from: {raw_input})",
            file=sys.stderr,
        )
        return 1

    # Extract and parse intervals
    try:
        data = {"intervals": data} if not isinstance(data, dict) else data
        intervals = parse_intervals_from_json(data["intervals"])
    except (ValueError, TypeError) as e:
        print(f"Error parsing intervals: {e}", file=sys.stderr)
        return 1

    # Merge
    try:
        result = merge_intervals(intervals)
    except Exception as e:
        print(f"Error merging intervals: {e}", file=sys.stderr)
        return 1

    # Write output
    output_json = json.dumps(result, ensure_ascii=False)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json + "\n")
        except OSError as e:
            print(f"Error writing to {args.output}: {e}", file=sys.stderr)
            return 1
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
