#!/usr/bin/env python3
import argparse
import csv
from collections import defaultdict


def main():
    parser = argparse.ArgumentParser(description="Sales summary CLI")
    parser.add_argument("--input", required=True, help="Path to CSV file with columns date,item,price,qty,city")
    parser.add_argument("--city", default=None, help="Restrict rows to a specific city")
    parser.add_argument("--top", type=int, default=5, help="Number of top items to print (default: 5)")
    args = parser.parse_args()

    revenue = defaultdict(float)

    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            item = row["item"]
            price = float(row["price"])
            qty = int(row["qty"])
            if args.city and row.get("city", "").strip() != args.city.strip():
                continue
            revenue[item] += price * qty

    # Sort by revenue descending, ties broken by item name ascending
    sorted_items = sorted(revenue.items(), key=lambda x: (-x[1], x[0]))

    for item, rev in sorted_items[:args.top]:
        print(f"{item}:{rev:.2f}")


if __name__ == "__main__":
    main()
