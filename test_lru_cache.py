import pytest
from lru_cache import LRUCache


def test_basic_get_put():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert c.get("missing") is None


def test_eviction_order():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # capacity 2 -> "a" (least recently used) evicted
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")       # "a" is now most recently used
    c.put("c", 3)     # should evict "b", not "a"
    assert c.get("b") is None
    assert c.get("a") == 1
    assert c.get("c") == 3


def test_put_existing_key_updates_value_and_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 99)    # update + refresh recency
    c.put("c", 3)     # should evict "b"
    assert c.get("a") == 99
    assert c.get("b") is None
    assert c.get("c") == 3


def test_invalidate():
    c = LRUCache(2)
    c.put("a", 1)
    assert "a" in c
    assert c.invalidate("a") is True
    assert "a" not in c
    assert c.get("a") is None
    assert c.invalidate("nonexistent") is False


def test_recency_order_listing():
    c = LRUCache(3)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    c.get("a")  # a becomes most recent
    assert c.keys_in_recency_order() == ["a", "c", "b"]


def test_capacity_validation():
    with pytest.raises(ValueError):
        LRUCache(0)


def test_len():
    c = LRUCache(5)
    c.put("a", 1)
    c.put("b", 2)
    assert len(c) == 2
