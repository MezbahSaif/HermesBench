#!/usr/bin/env python3
"""JSON pretty-printer CLI tool."""

import argparse
import json


def main():
    parser = argparse.ArgumentParser(
        description='Pretty-print JSON files to stdout.'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to a JSON file'
    )
    parser.add_argument(
        '--sort', '-s',
        action='store_true',
        default=False,
        help='Sort keys alphabetically at every nesting level'
    )

    args = parser.parse_args()

    with open(args.input, 'r') as f:
        data = json.load(f)

    if args.sort:
        def sort_keys(obj):
            if isinstance(obj, dict):
                return {k: sort_keys(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                return [sort_keys(item) for item in obj]
            else:
                return obj

        data = sort_keys(data)

    print(json.dumps(data, indent=2))


if __name__ == '__main__':
    main()
