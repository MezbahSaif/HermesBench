"""Output formatting for log level summaries."""


def format_summary(counts: dict[str, int], sort_key: str = "-count") -> list[str]:
    """Format counted levels into a sorted summary list.

    Args:
        counts: Dictionary of {level: count}.
        sort_key: Sort specification. Defaults to '-count' (descending by count).

    Returns:
        List of strings formatted as "LEVEL:COUNT", sorted by the key criteria.
        An empty dict returns an empty list (graceful fallback).

    Raises:
        ValueError: If a sort_key is provided that doesn't map to 'count'.
    """
    items = list(counts.items())

    # Sort logic: '-' prefix means descending, otherwise ascending
    reverse = sort_key.startswith("-")
    key_field = sort_key.lstrip("-").lower()  # e.g., 'count' or '-count'

    def sort_fn(item):
        if key_field == "count":
            return item[1]  # count value
        raise ValueError(
            f"Unsupported sort field '{key_field}'. Use 'count' (or '-count')."
        )

    items.sort(key=sort_fn, reverse=reverse)

    return [f"{lvl}:{cnt}" for lvl, cnt in items]
