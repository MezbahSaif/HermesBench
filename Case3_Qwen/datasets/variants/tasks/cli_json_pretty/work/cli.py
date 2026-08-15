#!/usr/bin/env python3
import argparse
import json
import sys


def sort_keys(obj):
    """Recursively sort dictionary keys at every nesting level."""
    if isinstance(obj, dict):
        return {k: sort_keys(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [sort_keys(item) for item in obj]
    else:
        return obj


def main():
    parser = argparse.ArgumentParser(description="Pretty-print JSON to stdout")
    parser.add_argument("--input", required=True, help="Path to a JSON file")
    parser.add_argument("--sort", action="store_true", help="Sort keys alphabetically at every nesting level")

    args = parser.parse_args()

    with open(args.input, "r") as f:
        data = json.load(f)

    if args.sort:
        data = sort_keys(data)

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
