import argparse
import csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to CSV file")
    parser.add_argument("--min-age", type=int, default=None, help="Minimum age filter")
    parser.add_argument("--job", default=None, help="Job filter (case-insensitive)")
    args = parser.parse_args()

    with open(args.input, newline="") as f:
        reader = csv.DictReader(f)
        matches = []
        for row in reader:
            row = {k: v.rstrip("\r") for k, v in row.items()}
            if args.min_age is not None and int(row["age"]) < args.min_age:
                continue
            if args.job is not None and row["job"].lower() != args.job.lower():
                continue
            matches.append(row["name"])

    for name in sorted(set(matches)):
        print(name)


if __name__ == "__main__":
    main()
