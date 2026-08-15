#!/usr/bin/env python3
"""CLI Word Frequency Counter.

Reads text from a file or stdin, tokenizes words (lowercased, alphabetic only),
counts frequencies, and prints sorted results.

Usage:
    python solution.py <file.txt>
    cat input.txt | python solution.py -
    echo "hello world" | python solution.py -
"""

import argparse
import collections
import re
import sys


def tokenize(text):
    """Tokenize text into lowercase alphabetic words."""
    return re.findall(r'[a-z]+', text.lower())


def count_words(words):
    """Count word frequencies using Counter."""
    return collections.Counter(words)


def format_output(counter, top_n=None):
    """Format the counter output as sorted lines.

    Sorted by descending frequency, with alphabetical tiebreaking.
    If top_n is specified (e.g., -n 5), only show top_n results.
    """
    if not counter:
        return ""
    sorted_words = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
    if top_n and top_n > 0:
        sorted_words = sorted_words[:top_n]
    lines = [f"{word} {count}" for word, count in sorted_words]
    return "\n".join(lines)


def read_input(source):
    """Read text from a file path or stdin."""
    if source == "-":
        data = sys.stdin.read()
    else:
        with open(source, "r", encoding="utf-8") as f:
            data = f.read()
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Count word frequencies in text. "
                    "Reads from a file or stdin (-). "
                    "Uses only alphabetic characters (case-insensitive)."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Input file path, or '-' to read from stdin (default: '-')"
    )
    parser.add_argument(
        "-n", "--top",
        type=int,
        default=None,
        metavar="N",
        help="Show only the top N most common words"
    )

    args = parser.parse_args()

    try:
        data = read_input(args.input)
    except FileNotFoundError:
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    words = tokenize(data)
    counter = count_words(words)

    output = format_output(counter, top_n=args.top)
    if output:
        print(output)


if __name__ == "__main__":
    main()
