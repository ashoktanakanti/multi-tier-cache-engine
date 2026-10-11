import threading
import time

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



# ---- (A) L1 expiry ---------------------------------------------------------
class FakeClock:
    """A clock the test moves forward by hand, so nothing has to sleep."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_l1_entries_expire():
    clock = FakeClock()
    cache = TieredCache(l1_ttl=30, clock=clock)
    cache.lookup("k", lambda: "v")
    clock.now = 29
    assert cache.lookup("k", lambda: "v")[1] == "l1"
    clock.now = 31
    assert cache.lookup("k", lambda: "v")[1] == "db"  # expired, reloaded


def test_other_servers_stale_copy_lasts_at_most_the_ttl():
    """Server A handles a write; server B's L1 copy can only be stale until it expires."""
    clock = FakeClock()
    shared = fakeredis.FakeServer()
    server_a = TieredCache(l1_ttl=30, clock=clock,
                           l2=RedisTier(fakeredis.FakeRedis(server=shared, decode_responses=True)))
    server_b = TieredCache(l1_ttl=30, clock=clock,
                           l2=RedisTier(fakeredis.FakeRedis(server=shared, decode_responses=True)))
    database = {"value": "old"}
    server_a.lookup("k", lambda: database["value"])
    server_b.lookup("k", lambda: database["value"])

    database["value"] = "new"
    server_a.invalidate("k")  # clears A's L1 and the shared Redis, but not B's L1

    assert server_a.get("k", lambda: database["value"]) == "new"
    assert server_b.get("k", lambda: database["value"]) == "old"  # the known gap...
    clock.now = 31
    assert server_b.get("k", lambda: database["value"]) == "new"  # ...closed by the TTL


# ---- (B) read/write race -----------------------------------------------------
def test_write_during_a_slow_read_is_not_cached(fake_redis):
    """
    1. A read misses and starts querying (it sees the OLD value).
    2. A write commits and invalidates the key.
    3. The read finishes. It must NOT leave the old value in the cache.
    """
    cache = TieredCache(l2=fake_redis)
    database = {"value": "old"}
    read_has_queried, write_done = threading.Event(), threading.Event()

    def slow_loader():
        value = database["value"]  # reads "old"
        read_has_queried.set()
        write_done.wait()  # the write happens while we are still "computing"
        return value

    reader = threading.Thread(target=lambda: cache.lookup("k", slow_loader))
    reader.start()
    read_has_queried.wait()
    database["value"] = "new"
    cache.invalidate("k")
    write_done.set()
    reader.join()

    assert "k" not in cache.l1
    assert fake_redis.get("k") is None
    assert cache.lookup("k", lambda: database["value"])[:2] == ("new", "db")


# ---- (C) stampede ------------------------------------------------------------
def test_many_misses_on_one_key_run_one_query():
    cache = TieredCache()
    calls = []

    def slow_loader():
        calls.append(1)
        time.sleep(0.2)
        return "summary"

    start = threading.Barrier(20)
    results = []

    def request():
        start.wait()  # all 20 requests miss at the same moment
        results.append(cache.lookup("k", slow_loader)[:2])

    threads = [threading.Thread(target=request) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(calls) == 1  # one database query, not 20
    assert [v for v, _ in results] == ["summary"] * 20
    assert sorted(s for _, s in results) == ["db"] + ["l1"] * 19


def test_if_the_first_query_fails_the_others_still_get_an_answer():
    cache = TieredCache()
    first_started = threading.Event()
    results = []

    def failing_loader():
        first_started.set()
        time.sleep(0.1)
        raise RuntimeError("database timeout")

    def waiter():
        first_started.wait()
        results.append(cache.get("k", lambda: "recovered"))

    t = threading.Thread(target=waiter)
    t.start()
    with pytest.raises(RuntimeError):
        cache.get("k", failing_loader)
    t.join()
    assert results == ["recovered"]
