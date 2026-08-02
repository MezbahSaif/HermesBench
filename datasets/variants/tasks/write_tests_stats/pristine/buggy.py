def median(values):
    """Median without mutating the input list."""
    if not values:
        raise ValueError("empty list")
    values.sort()
    n = len(values)
    mid = n // 2
    if n % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def mean(values):
    if not values:
        raise ValueError("empty list")
    return sum(values) / len(values)
