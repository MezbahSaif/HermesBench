#!/usr/bin/env python3
import argparse
import csv


def main():
    parser = argparse.ArgumentParser(description='CSV filter CLI')
    parser.add_argument('--input', required=True, help='path to CSV file with columns name,age,city,job')
    parser.add_argument('--min-age', type=int, default=None, help='only people with age >= N')
    parser.add_argument('--job', default=None, help='only people whose job equals JOB (case-insensitive)')
    
    args = parser.parse_args()
    
    # Read CSV
    people = []
    with open(args.input, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['name']
            age = int(row['age'])
            job = row['job'].lower()  # normalize for case-insensitive comparison
            people.append((name, age, job))
    
    # Apply filters
    filtered = []
    for name, age, job in people:
        if args.min_age is not None and age < args.min_age:
            continue
        if args.job is not None and job != args.job.lower():
            continue
        filtered.append(name)
    
    # Sort alphabetically and print
    for name in sorted(filtered):
        print(name)


if __name__ == '__main__':
    main()
