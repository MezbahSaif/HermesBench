#!/usr/bin/env python3
"""CLI entry point for the log summarizer."""

import os
import sys


def print_usage():
    """Print usage instructions."""
    print("Usage: python cli.py <file1.txt> [file2.txt ...] | input from stdin")
    print("")
    print("Reads text files passed as positional arguments or reads from stdin.")
    print("Outputs sorted LEVEL:COUNT summary of log lines.")


def summarize(lines):
    """Summarize log lines into a sorted list of LEVEL:COUNT strings.

    Uses the existing counter.py and formatter.py modules.

    Args:
        lines: List of log lines (expected format: "<level> <message>").

    Returns:
        Sorted list of "LEVEL:COUNT" strings, sorted by count descending.

    Raises:
        ValueError: If any line cannot be parsed or if counts are empty.
    """
    from counter import count_levels
    from formatter import format_summary

    counts = count_levels(lines)
    return format_summary(counts)


def read_lines_from_file(path):
    """Read lines from a file, trying multiple path forms for compatibility."""
    paths_to_try = [path]
    if not os.path.exists(path):
        # Try relative from the script's directory
        cwd = str(os.path.dirname(os.path.abspath(__file__)))
        rel = os.path.relpath(path, cwd)
        if not os.path.exists(rel):
            paths_to_try.append(rel)

    for candidate in paths_to_try:
        try:
            with open(candidate) as fh:
                return fh.readlines()
        except (FileNotFoundError, OSError):
            continue

    # Last resort: try with the script's dir as base
    cwd = str(os.path.dirname(os.path.abspath(__file__)))
    rel = os.path.relpath(path, cwd) if not path.startswith('/') else path
    for candidate in [rel, path]:
        try:
            with open(candidate) as fh:
                return fh.readlines()
        except (FileNotFoundError, OSError):
            continue

    raise FileNotFoundError(f"Could not read file: {path}")


def main():
    """Main CLI entry point."""
    files = [str(f) for f in sys.argv[1:]]

    # Read lines from files or stdin
    all_lines = []
    if not files:
        # No positional arguments — read from stdin
        all_lines.extend(sys.stdin.readlines())
    else:
        for file_path in files:
            try:
                all_lines.extend(read_lines_from_file(file_path))
            except FileNotFoundError as e:
                print(str(e), file=sys.stderr)
                sys.exit(1)

    if not all_lines:
        print("No data provided. Please provide log files or pipe input.")
        sys.exit(1)

    # Process through the summarizer pipeline
    results = summarize(all_lines)
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
