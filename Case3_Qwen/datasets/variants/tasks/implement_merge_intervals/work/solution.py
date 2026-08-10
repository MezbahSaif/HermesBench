def merge_intervals(intervals: list[list[int]]) -> list[list[int]]:
    """Merge all overlapping intervals and return them sorted by start.
    Touching intervals ([1,2] and [2,3]) merge as well.

    Example: merge_intervals([[1, 3], [2, 6], [8, 10], [15, 18]])
             == [[1, 6], [8, 10], [15, 18]]
    """
    # Edge case: empty input
    if not intervals:
        return []
    
    # Sort by start time
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    
    merged = [sorted_intervals[0][:]]  # Copy first interval
    
    for current in sorted_intervals[1:]:
        prev = merged[-1]
        # Merge if touching or overlapping (current start <= prev end + 1)
        if current[0] <= prev[1] + 1:
            # Extend the previous interval's end if needed
            prev[1] = max(prev[1], current[1])
        else:
            # No overlap, add new interval (copy to avoid mutation issues)
            merged.append(current[:])
    
    return merged
