"""Log level counting logic - separated from formatting concerns."""


def count_levels(lines: list[str]) -> dict[str, int]:
    """Count occurrences of each log level in a collection of lines.

    Each line should have the format where the level is at index 1 when
    split by spaces (e.g., " INFO message" -> "INFO").

    Args:
        lines: List of log lines to analyze.

    Returns:
        Dictionary mapping each unique log level to its occurrence count.

    Raises:
        ValueError: If a line cannot be parsed into a recognizable level field.
                    For example, if the split result doesn't have enough parts.
    """
    counts = {}
    for line in lines:
        parts = line.split(" ")
        # Expecting at least 2 parts: <level> <message>
        if len(parts) < 2:
            raise ValueError(
                f"Cannot parse log level from line: '{line}' "
                "(expected format: '<LEVEL> <message>')"
            )
        lvl = parts[1]
        counts[lvl] = counts.get(lvl, 0) + 1
    return counts
