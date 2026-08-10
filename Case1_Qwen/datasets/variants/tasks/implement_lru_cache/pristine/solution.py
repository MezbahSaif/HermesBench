from collections import OrderedDict


class LRUCache:
    """Least-recently-used cache with fixed capacity (>= 1).

    get(key) returns the stored value or -1. Every get/put refreshes
    recency. put(key, value) inserts/updates and evicts the
    least-recently-used entry when at capacity.
    """

    def __init__(self, capacity: int):
        raise NotImplementedError

    def get(self, key: int) -> int:
        raise NotImplementedError

    def put(self, key: int, value: int) -> None:
        raise NotImplementedError
