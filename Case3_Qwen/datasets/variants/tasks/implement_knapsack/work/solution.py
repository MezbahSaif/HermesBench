#!/usr/bin/env python3
"""0/1 Knapsack Solver CLI

Solves the 0/1 knapsack problem using dynamic programming.
Reads input from file arguments or stdin, outputs max values sorted by frequency.

Usage:
    python solution.py <file1.txt> [file2.txt ...]
    echo "capacity,weight,value" | python solution.py -

Input format (per line): capacity,weight1,value1,...,weightN,valueN
Output: results sorted by descending value with alphabetical tiebreaking.
"""

import sys
from collections import Counter


def parse_input(text: str) -> list[dict]:
    """Parse input text into a list of problem instances."""
    if not text.strip():
        return []

    # Normalize line endings and skip blank lines
    lines = [l for l in text.replace('\r\n', '\n').replace('\r', '\n').split('\n') if l.strip()]

    problems = []
    for i, line in enumerate(lines, 1):
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 3:
            raise ValueError(f"Line {i}: Need at least capacity and one weight-value pair")

        try:
            capacity = int(parts[0])
        except ValueError:
            raise ValueError(f"Line {i}: Invalid capacity '{parts[0]}'")

        weights, values = [], []
        idx = 1
        while idx + 1 < len(parts):
            try:
                w, v = int(parts[idx]), int(parts[idx + 1])
                if w < 0 or v < 0:
                    raise ValueError(f"Line {i}: Negative weight or value not allowed")
                weights.append(w)
                values.append(v)
                idx += 2
            except ValueError as e:
                raise ValueError(f"Line {i}: Invalid format — {e}")

        if len(weights) != len(values):
            raise ValueError(f"Line {i}: Weight and value count mismatch")

        problems.append({
            'capacity': capacity,
            'weights': weights,
            'values': values,
        })
    return problems


def knapsack(capacity: int, weights: list[int], values: list[int]) -> int:
    """Return the maximum total value achievable with total weight <= capacity.

    Each item may be used at most once (0/1 knapsack).

    Example: knapsack(10, [5, 4, 6, 3], [10, 40, 30, 50]) == 90
    """
    if capacity < 0 or len(weights) != len(values):
        raise ValueError("Invalid input: capacity must be non-negative and weights/values must have equal length")

    n = len(weights)
    dp = [0] * (capacity + 1)
    for i in range(n):
        w_i, v_i = weights[i], values[i]
        for w in range(capacity, w_i - 1, -1):
            dp[w] = max(dp[w], dp[w - w_i] + v_i)

    return dp[capacity]


def main():
    """CLI entry point."""
    # Determine input source: files or stdin
    if len(sys.argv) > 1:
        text_parts = []
        for filename in sys.argv[1:]:
            try:
                with open(filename, 'r') as f:
                    content = f.read()
                    if text_parts:
                        text_parts.append('\n' + content)
                    else:
                        text_parts.append(content)
            except FileNotFoundError:
                print(f"Error: File '{filename}' not found.", file=sys.stderr)
                sys.exit(1)
        input_text = ''.join(text_parts)
    elif len(sys.argv) == 1 and not sys.stdin.isatty():
        input_text = sys.stdin.read()
    else:
        print("Usage:\n  python solution.py <file1.txt> [file2.txt ...]\n  echo 'data' | python solution.py -", file=sys.stderr)
        sys.exit(1)

    if not input_text.strip():
        print("Error: No input provided.", file=sys.stderr)
        print("Usage:\n  python solution.py <file1.txt> [file2.txt ...]\n  echo 'data' | python solution.py -", file=sys.stderr)
        sys.exit(1)

    # Parse and validate problems
    try:
        problems = parse_input(input_text)
    except ValueError as e:
        print(f"Error parsing input: {e}", file=sys.stderr)
        sys.exit(1)

    if not problems:
        print("Error: No valid problems found in input.", file=sys.stderr)
        sys.exit(1)

    # Solve each problem
    results = []
    for i, prob in enumerate(problems):
        try:
            val = knapsack(prob['capacity'], prob['weights'], prob['values'])
            results.append((i + 1, val))
        except ValueError as e:
            print(f"Error solving problem {i+1}: {e}", file=sys.stderr)

    if not results:
        print("Error: No problems could be solved.", file=sys.stderr)
        sys.exit(1)

    # Sort by descending frequency (value), then alphabetical tiebreaking on index
    counter = Counter(val for _, val in results)
    sorted_results = sorted(counter.items(), key=lambda x: (-x[1], str(x[0])))

    for rank, value in sorted_results:
        print(f"Problem {rank}: Maximum value = {value}")


if __name__ == '__main__':
    main()
