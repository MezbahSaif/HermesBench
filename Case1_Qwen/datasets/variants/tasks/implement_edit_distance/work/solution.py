def edit_distance(a: str, b: str) -> int:
    """Return the Levenshtein distance between a and b: the minimum number
    of single-character insertions, deletions or substitutions needed to
    turn a into b.

    Example: edit_distance("kitten", "sitting") == 3
    """
    if len(a) < len(b):
        return edit_distance(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        curr = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1,       # deletion
                          curr[j - 1] + 1,    # insertion
                          prev[j - 1] + cost) # substitution
        prev = curr
    return prev[len(b)]
