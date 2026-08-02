# Word frequency CLI

`cli.py --input FILE [--top N]`

- `--input` (required): path to a plain-text file
- `--top N` (optional, default 10): print the N most frequent words

Words are lowercased and stripped of surrounding punctuation
(.,!?;:"'()). Print `word:count` per line, most frequent first, ties
broken alphabetically.
