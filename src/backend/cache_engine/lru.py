"""
LRUCache — Least Recently Used cache, built from scratch.

Data structures:
  - dict (hash map): key -> node, so we can find any key in O(1)
  - doubly linked list: keeps keys in order of use
        head <-> most recently used ... least recently used <-> tail

get(key): move the node to the front                          O(1)
put(key): add at the front; if full, remove the node before tail O(1)

A lock makes each operation thread-safe, because FastAPI handles
requests on several threads at once.
"""
import threading


class _Node:
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = capacity
        self.map = {}
        self.lock = threading.Lock()

        # Dummy head/tail nodes so we never have to handle an empty list specially.
        self.head = _Node()
        self.tail = _Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_to_front(self, node):
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key):
        with self.lock:
            node = self.map.get(key)
            if node is None:
                return None
            self._remove(node)
            self._add_to_front(node)
            return node.value

    def put(self, key, value):
        """Insert or update a key. Returns the evicted key, or None."""
        with self.lock:
            if key in self.map:
                node = self.map[key]
                node.value = value
                self._remove(node)
                self._add_to_front(node)
                return None

            evicted = None
            if len(self.map) >= self.capacity:
                lru = self.tail.prev
                self._remove(lru)
                del self.map[lru.key]
                evicted = lru.key

            node = _Node(key, value)
            self.map[key] = node
            self._add_to_front(node)
            return evicted

    def delete(self, key) -> bool:
        with self.lock:
            node = self.map.pop(key, None)
            if node is None:
                return False
            self._remove(node)
            return True

    def clear(self):
        with self.lock:
            self.map.clear()
            self.head.next = self.tail
            self.tail.prev = self.head

    def __contains__(self, key):
        return key in self.map

    def __len__(self):
        return len(self.map)

    def keys(self):
        """Keys from most to least recently used (useful for tests)."""
        out, node = [], self.head.next
        while node is not self.tail:
            out.append(node.key)
            node = node.next
        return out
