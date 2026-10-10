import pytest

from cache_engine import LFUCache


def test_get_and_put():
    c = LFUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1
    assert c.get("missing") is None


def test_evicts_least_frequently_used():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")  # a used twice, b once
    assert c.put("c", 3) == "b"


def test_tie_goes_to_the_oldest_key():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.put("c", 3) == "a"


def test_popular_key_survives_a_burst_of_new_keys():
    """The reason to choose LFU: one-off keys can't push out a popular one."""
    c = LFUCache(3)
    c.put("popular", 1)
    for _ in range(5):
        c.get("popular")
    for i in range(20):
        c.put(f"one-off-{i}", i)
    assert c.get("popular") == 1


def test_delete_then_fill_up():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("b")
    assert c.delete("a") is True
    c.put("c", 3)
    assert c.put("d", 4) == "c"
    assert c.get("b") == 2


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        LFUCache(0)
