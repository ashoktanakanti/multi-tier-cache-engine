"""
LFUCache — evicts the Least Frequently Used key instead of the least
recently used one. Built with the classic O(1) frequency-bucket design:

  - key_map:   key -> (value, freq)                     O(1) lookup
  - freq_map:  freq -> OrderedDict of keys at that freq  O(1) insert/remove
  - min_freq:  tracks the lowest frequency currently in use

get(key):  bump the key's frequency bucket, O(1).
put(key):  insert at freq=1; if over capacity, evict the oldest key in the
           min_freq bucket (ties broken by insertion order), O(1).

Where LRU only cares about "was this used recently", LFU cares about
"how often is this used overall" — better for data with a small set of
consistently hot items that doesn't shift over time, worse for bursty
access patterns (a good discussion point vs. LRU in the README).
"""
from __future__ import annotations
from collections import OrderedDict, defaultdict


class LFUCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.key_map: dict[object, tuple] = {}          # key -> (value, freq)
        self.freq_map: dict[int, OrderedDict] = defaultdict(OrderedDict)  # freq -> {key: True}
        self.min_freq = 0

    def _bump_freq(self, key: object) -> None:
        value, freq = self.key_map[key]
        del self.freq_map[freq][key]
        if not self.freq_map[freq]:
            del self.freq_map[freq]
            if self.min_freq == freq:
                self.min_freq += 1
        new_freq = freq + 1
        self.freq_map[new_freq][key] = True
        self.key_map[key] = (value, new_freq)

    def get(self, key):
        if key not in self.key_map:
            return None
        value, _ = self.key_map[key]
        self._bump_freq(key)
        return value

    def put(self, key, value) -> None:
        if key in self.key_map:
            _, freq = self.key_map[key]
            self.key_map[key] = (value, freq)
            self._bump_freq(key)
            return

        if len(self.key_map) >= self.capacity:
            evict_key, _ = self.freq_map[self.min_freq].popitem(last=False)
            if not self.freq_map[self.min_freq]:
                del self.freq_map[self.min_freq]
            del self.key_map[evict_key]

        self.key_map[key] = (value, 1)
        self.freq_map[1][key] = True
        self.min_freq = 1

    def invalidate(self, key) -> bool:
        if key not in self.key_map:
            return False
        _, freq = self.key_map.pop(key)
        del self.freq_map[freq][key]
        if not self.freq_map[freq]:
            del self.freq_map[freq]
        return True

    def __contains__(self, key) -> bool:
        return key in self.key_map

    def __len__(self) -> int:
        return len(self.key_map)
