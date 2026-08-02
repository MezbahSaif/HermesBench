def median(values):
    """Median without mutating the input list."""
    if not values:
        raise ValueError("empty list")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def mean(values):
    if not values:
        raise ValueError("empty list")
    return sum(values) / len(values)
