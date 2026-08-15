def max_profit(prices: list[float]) -> float:
    """Return the maximum profit achievable by buying once and selling once
    later (sell index must be after buy index). Return 0.0 if impossible.

    Example: max_profit([7, 1, 5, 3, 6, 4]) == 5.0
    """
    if not prices or len(prices) < 2:
        return 0.0

    min_price = prices[0]
    max_profit_val = 0.0

    for price in prices[1:]:
        profit = price - min_price
        if profit > max_profit_val:
            max_profit_val = profit
        elif price < min_price:
            min_price = price

    return max_profit_val
