# CSV filter CLI

`cli.py --input FILE [--min-age N] [--job JOB]`

- `--input` (required): path to a CSV with columns name,age,city,job
- `--min-age N` (optional): only people with age >= N
- `--job JOB` (optional): only people whose job equals JOB (case-insensitive)

Print matching names sorted alphabetically, one per line.
