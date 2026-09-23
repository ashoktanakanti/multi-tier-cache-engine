"""
LRUCache — the "small toy basket" — built from scratch with core DSA:

  - A hash map (dict) for O(1) lookup of a key's node.
  - A doubly linked list to track recency order in O(1):
      head <-> most-recently-used ... least-recently-used <-> tail

get(key):  move the node to the front (most recent), O(1).
put(key):  insert at front; if capacity exceeded, evict the tail's
           neighbour (least recently used), O(1).

No dict.move_to_end() or OrderedDict shortcuts — the linked list is
built and rewired by hand so the mechanics are fully explicit.
"""
from __future__ import annotations


class _Node:
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev: "_Node | None" = None
        self.next: "_Node | None" = None


class LRUCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.map: dict[object, _Node] = {}

        # Sentinel head/tail so we never special-case empty-list edges.
        self.head = _Node()
        self.tail = _Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    # ---- internal linked-list helpers -------------------------------
    def _remove(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_to_front(self, node: _Node) -> None:
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    # ---- public API ---------------------------------------------------
    def get(self, key):
        node = self.map.get(key)
        if node is None:
            return None
        self._remove(node)
        self._add_to_front(node)
        return node.value

    def put(self, key, value) -> None:
        if key in self.map:
            node = self.map[key]
            node.value = value
            self._remove(node)
            self._add_to_front(node)
            return

        if len(self.map) >= self.capacity:
            lru_node = self.tail.prev
            self._remove(lru_node)
            del self.map[lru_node.key]

        node = _Node(key, value)
        self.map[key] = node
        self._add_to_front(node)

    def invalidate(self, key) -> bool:
        """Remove a key immediately (used when the underlying row changes)."""
        node = self.map.pop(key, None)
        if node is None:
            return False
        self._remove(node)
        return True

    def __contains__(self, key) -> bool:
        return key in self.map

    def __len__(self) -> int:
        return len(self.map)

    def keys_in_recency_order(self) -> list:
        """Most-recently-used first — handy for tests/debugging."""
        out = []
        node = self.head.next
        while node is not self.tail:
            out.append(node.key)
            node = node.next
        return out
