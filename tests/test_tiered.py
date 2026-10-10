import fakeredis
import pytest

from cache_engine import RedisTier, TieredCache


class CountingLoader:
    """Pretend database: counts how often it was queried."""

    def __init__(self, value):
        self.value = value
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.value


def test_first_read_from_db_then_l1():
    cache = TieredCache()
    loader = CountingLoader({"x": 1})
    assert cache.lookup("k", loader)[:2] == ({"x": 1}, "db")
    assert cache.lookup("k", loader)[:2] == ({"x": 1}, "l1")
    assert loader.calls == 1


def test_steps_show_the_path_through_the_tiers(fake_redis):
    cache = TieredCache(l2=fake_redis)
    _, _, steps = cache.lookup("k", lambda: "v")
    assert [(s["tier"], s["result"]) for s in steps] == [
        ("l1", "miss"), ("l2", "miss"), ("db", "found"), ("l2", "write"), ("l1", "write")]

    cache.l1.clear()  # simulate a different server process with an empty L1
    _, source, steps = cache.lookup("k", lambda: "v")
    assert source == "l2"
    assert [(s["tier"], s["result"]) for s in steps] == [("l1", "miss"), ("l2", "hit"), ("l1", "write")]


def test_two_servers_share_l2():
    shared = fakeredis.FakeServer()
    server_a = TieredCache(l2=RedisTier(fakeredis.FakeRedis(server=shared, decode_responses=True)))
    server_b = TieredCache(l2=RedisTier(fakeredis.FakeRedis(server=shared, decode_responses=True)))
    loader = CountingLoader([1, 2, 3])

    server_a.lookup("k", loader)
    assert server_b.lookup("k", loader)[1] == "l2"
    assert loader.calls == 1  # server B never touched the database


def test_invalidate_removes_key_from_every_tier(fake_redis):
    cache = TieredCache(l2=fake_redis)
    cache.lookup("k", lambda: "old")
    cache.invalidate("k")
    assert "k" not in cache.l1
    assert fake_redis.get("k") is None
    assert cache.lookup("k", lambda: "new")[:2] == ("new", "db")


def test_missing_values_are_not_cached():
    cache = TieredCache()
    loader = CountingLoader(None)
    cache.lookup("k", loader)
    cache.lookup("k", loader)
    assert loader.calls == 2


def test_redis_down_falls_back_to_database():
    server = fakeredis.FakeServer()
    tier = RedisTier(fakeredis.FakeRedis(server=server, decode_responses=True))
    server.connected = False  # Redis "crashes"
    assert tier.get("k") is None  # a miss, not an exception
    tier.put("k", 1)  # silently skipped
    tier.delete("k")
    assert tier.ping() is False

    cache = TieredCache(l2=tier)
    assert cache.lookup("k", lambda: "v")[:2] == ("v", "db")
    assert cache.lookup("k", lambda: "v")[:2] == ("v", "l1")


def test_stats_and_eviction_events():
    cache = TieredCache(l1_capacity=1)
    cache.lookup("a", lambda: 1)
    cache.lookup("a", lambda: 1)
    cache.lookup("b", lambda: 2)  # evicts "a"

    stats = cache.stats()
    assert stats["hits"] == {"l1": 1, "l2": 0, "db": 2}
    assert stats["hit_ratio"] == pytest.approx(1 / 3, abs=1e-3)
    assert stats["evictions"] == 1
    kinds = [e["kind"] for e in cache.events_after(0)]
    assert kinds == ["load", "hit", "evict", "load"]


def test_event_log_is_incremental():
    cache = TieredCache()
    cache.lookup("a", lambda: 1)
    last = cache.events_after(0)[-1]["seq"]
    cache.lookup("b", lambda: 2)
    assert [e["key"] for e in cache.events_after(last)] == ["b"]


def test_lfu_policy_and_bad_policy():
    assert TieredCache(policy="lfu").policy == "lfu"
    with pytest.raises(ValueError):
        TieredCache(policy="fifo")

