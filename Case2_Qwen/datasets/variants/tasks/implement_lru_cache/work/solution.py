from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache with fixed capacity (>= 1).

    get(key) returns the stored value or -1. Every get/put refreshes
    recency. put(key, value) inserts/updates and evicts the
    least-recently-used entry when at capacity.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key: int) -> int:
        """Return value if key exists and is within capacity, else -1.
        Refreshes recency by moving accessed key to end (most recent)."""
        if key not in self.cache:
            return -1
        # Move accessed key to end (most recently used)
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: int, value: int) -> None:
        """Insert or update key-value. Evict LRU entry if at capacity."""
        if key in self.cache:
            # Update existing key and move to end (most recently used)
            self.cache.move_to_end(key)
            self.cache[key] = value
        else:
            # New key - check capacity
            if len(self.cache) >= self.capacity:
                # Remove least recently used (first item)
                self.cache.popitem(last=False)
            self.cache[key] = value
