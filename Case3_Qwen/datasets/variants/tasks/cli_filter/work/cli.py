#!/usr/bin/env python3
import argparse
import csv


def main():
    parser = argparse.ArgumentParser(description='Filter people from CSV')
    parser.add_argument('--input', required=True, help='Path to CSV file with columns: name,age,city,job')
    parser.add_argument('--min-age', type=int, default=None, help='Only people with age >= N')
    parser.add_argument('--job', default=None, help='Only people whose job equals JOB (case-insensitive)')
    
    args = parser.parse_args()
    
    # Read and filter CSV
    results = []
    with open(args.input, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            include = True
            
            if args.min_age is not None:
                age = int(row['age'])
                if age < args.min_age:
                    include = False
            
            if args.job is not None:
                if row['job'].strip().lower() != args.job.lower():
                    include = False
            
            if include:
                results.append(row['name'])
    
    # Sort and print names alphabetically
    for name in sorted(results):
        print(name)


if __name__ == '__main__':
    main()
