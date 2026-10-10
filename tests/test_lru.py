import threading

import pytest

from cache_engine import LRUCache


def test_get_and_put():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    assert c.get("b") == 2
    assert c.get("missing") is None


def test_evicts_least_recently_used():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.put("c", 3) == "a"  # put returns the evicted key
    assert c.get("a") is None


def test_get_makes_key_recent():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")  # now "b" is the least recently used
    assert c.put("c", 3) == "b"
    assert c.get("a") == 1


def test_updating_a_key_does_not_evict():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.put("a", 99) is None
    assert c.get("a") == 99 and len(c) == 2


def test_delete_and_clear():
    c = LRUCache(3)
    c.put("a", 1)
    c.put("b", 2)
    assert c.delete("a") is True
    assert c.delete("a") is False
    assert "a" not in c
    c.clear()
    assert len(c) == 0 and c.keys() == []


def test_recency_order():
    c = LRUCache(3)
    for k in "abc":
        c.put(k, k)
    c.get("a")
    assert c.keys() == ["a", "c", "b"]


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        LRUCache(0)


def test_many_threads_do_not_corrupt_the_list():
    c = LRUCache(16)

    def worker(n):
        for i in range(2000):
            key = (n * 7 + i) % 40
            c.put(key, i) if i % 3 else c.get(key)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(c.keys()) == len(c) <= 16
