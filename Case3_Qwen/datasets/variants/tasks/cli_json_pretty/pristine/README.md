# JSON pretty-printer CLI

`cli.py --input FILE [--sort]`

- `--input` (required): path to a JSON file
- `--sort` (optional): sort keys alphabetically at every nesting level

Print the JSON indented with 2 spaces to stdout. Without `--sort` the
original key order is preserved.
