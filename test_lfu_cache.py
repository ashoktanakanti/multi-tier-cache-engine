import pytest
from lfu_cache import LFUCache


def test_basic_get_put():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") == 1
    assert c.get("missing") is None


def test_evicts_least_frequently_used():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")        # freq(a)=2, freq(b)=1
    c.put("c", 3)      # capacity exceeded -> evict "b" (lowest freq)
    assert c.get("b") is None
    assert c.get("a") == 1
    assert c.get("c") == 3


def test_tie_breaks_by_insertion_order():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)      # both freq=1, "a" inserted first
    c.put("c", 3)      # tie -> evict "a" (oldest at min freq)
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_put_existing_key_bumps_frequency():
    c = LFUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 99)     # update bumps freq(a) to 2
    c.put("c", 3)      # evict "b" (freq=1), not "a"
    assert c.get("a") == 99
    assert c.get("b") is None
    assert c.get("c") == 3


def test_invalidate():
    c = LFUCache(2)
    c.put("a", 1)
    assert c.invalidate("a") is True
    assert "a" not in c
    assert c.invalidate("a") is False


def test_capacity_validation():
    with pytest.raises(ValueError):
        LFUCache(0)
