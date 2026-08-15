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
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return -1

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache.move_to_end(key)
            self.cache[key] = value
        else:
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
