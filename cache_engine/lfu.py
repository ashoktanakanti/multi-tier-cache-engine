"""
LFUCache — Least Frequently Used cache, O(1) get/put.

Data structures:
  - values:    key -> value
  - counts:    key -> how many times it was used
  - buckets:   count -> OrderedDict of keys with that count (oldest first)
  - min_count: the smallest count currently in the cache

When full, evict the oldest key in the min_count bucket.

LRU vs LFU: LRU keeps whatever was used recently; LFU keeps whatever is
used most often, so a burst of one-off keys can't push out a popular key.
Same interface as LRUCache, so the two are interchangeable.
"""
import threading
from collections import OrderedDict, defaultdict


class LFUCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.values = {}
        self.counts = {}
        self.buckets = defaultdict(OrderedDict)
        self.min_count = 0
        self.lock = threading.Lock()

    def _touch(self, key):
        """Move a key from bucket[count] to bucket[count + 1]."""
        count = self.counts[key]
        del self.buckets[count][key]
        if not self.buckets[count]:
            del self.buckets[count]
            if self.min_count == count:
                self.min_count = count + 1
        self.counts[key] = count + 1
        self.buckets[count + 1][key] = None

    def get(self, key):
        with self.lock:
            if key not in self.values:
                return None
            self._touch(key)
            return self.values[key]

    def put(self, key, value):
        """Insert or update a key. Returns the evicted key, or None."""
        with self.lock:
            if key in self.values:
                self.values[key] = value
                self._touch(key)
                return None

            evicted = None
            if len(self.values) >= self.capacity:
                if self.min_count not in self.buckets:  # can happen after delete()
                    self.min_count = min(self.buckets)
                evicted, _ = self.buckets[self.min_count].popitem(last=False)
                if not self.buckets[self.min_count]:
                    del self.buckets[self.min_count]
                del self.values[evicted]
                del self.counts[evicted]

            self.values[key] = value
            self.counts[key] = 1
            self.buckets[1][key] = None
            self.min_count = 1
            return evicted

    def delete(self, key) -> bool:
        with self.lock:
            if key not in self.values:
                return False
            count = self.counts.pop(key)
            del self.values[key]
            del self.buckets[count][key]
            if not self.buckets[count]:
                del self.buckets[count]
            return True

    def clear(self):
        with self.lock:
            self.values.clear()
            self.counts.clear()
            self.buckets.clear()
            self.min_count = 0

    def __contains__(self, key):
        return key in self.values

    def __len__(self):
        return len(self.values)
