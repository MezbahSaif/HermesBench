# Sales summary CLI

`cli.py --input FILE [--city CITY] [--top N]`

- `--input` (required): path to a CSV with columns date,item,price,qty,city
- `--city` (optional): restrict to rows with that city
- `--top N` (optional, default 5): print the N items with the highest total
  revenue (price * qty), one per line: `ITEM:REVENUE` (revenue rounded to 2
  decimals), sorted descending by revenue, ties broken by item name.

Example output for a small file with top 2:
Widget:10.50
Gadget:4.00
