def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    """Merge all overlapping intervals and return them sorted by start.
    Touching intervals ([1,2] and [2,3]) merge as well.

    Example: merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
             == [[1, 6], [8, 10], [15, 18]]
    """
    if not intervals:
        return []

    # Sort by start value
    intervals.sort(key=lambda x: x[0])

    merged = [intervals[0]]
    for current_start, current_end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        # Merge if overlapping or touching (current_start <= prev_end)
        if current_start <= prev_end:
            merged[-1] = [prev_start, max(prev_end, current_end)]
        else:
            merged.append([current_start, current_end])

    return merged
