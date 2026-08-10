def knapsack(capacity: int, weights: list[int], values: list[int]) -> int:
    """Return the maximum total value achievable with total weight
    <= capacity. Each item may be used at most once (0/1 knapsack).

    Example: knapsack(10, [5, 4, 6, 3], [10, 40, 30, 50]) == 90
    """
    # Edge cases
    if not weights or not values or capacity <= 0:
        return 0
    
    n = len(weights)
    if n != len(values):
        raise ValueError("weights and values must have the same length")
    
    # dp[w] = max value with weight limit w
    dp = [0] * (capacity + 1)
    
    for i in range(n):
        weight = weights[i]
        value = values[i]
        # Iterate backwards to avoid reusing the same item
        for w in range(capacity, weight - 1, -1):
            dp[w] = max(dp[w], dp[w - weight] + value)
    
    return dp[capacity]
