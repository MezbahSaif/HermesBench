#!/usr/bin/env python3
import argparse
import csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='Path to CSV file')
    parser.add_argument('--min-age', type=int, default=None, help='Minimum age filter')
    parser.add_argument('--job', type=str, default=None, help='Job filter (case-insensitive)')
    args = parser.parse_args()

    names = []
    with open(args.input, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['name']
            age = int(row['age'])
            job = row['job'].lower()

            if args.min_age is not None and age < args.min_age:
                continue
            if args.job is not None and job != args.job.lower():
                continue
            names.append(name)

    for name in sorted(names):
        print(name)


if __name__ == '__main__':
    main()
