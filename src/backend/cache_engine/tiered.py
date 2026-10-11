"""
TieredCache — the cache-aside pattern across three tiers.

Read path (lookup):
    1. L1  in-process LRU/LFU      ~microseconds
    2. L2  Redis (shared)           ~sub-millisecond
    3. DB  the loader function      tens of milliseconds
   On a DB read, the value is written into L2 and L1 on the way back.
   On an L2 hit, the value is copied (promoted) into L1.

Write path (invalidate):
   The caller writes to the database first, then calls invalidate(), which
   deletes the key from L1 and L2. The next read misses and reloads fresh
   data. This is "delete-on-write": simpler and safer than updating the
   cached copy in place.

Three protections on top of plain cache-aside:

  A. L1 expiry (TTL). invalidate() can only clear the L1 of the server that
     handled the write. Other servers' L1 copies expire after `l1_ttl`
     seconds, so stale data lives at most that long.

  B. Version number per key (read/write race). If a read starts computing,
     then a write commits and invalidates, the read must not save its old
     result afterwards. Every invalidate() bumps the key's version; a read
     remembers the version it started with and undoes its save if the
     version changed.

  C. Single-flight (stampede). If 50 requests miss the same key at once,
     only the first runs the database query; the others wait for it and
     then read its result from L1.

It also keeps hit counters, latencies and a short event log for the dashboard.
"""
import threading
import time
from collections import deque

from .lfu import LFUCache
from .lru import LRUCache


def _ms_since(start):
    return round((time.perf_counter() - start) * 1000, 4)


def _percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * pct / 100))], 4)


class TieredCache:
    def __init__(self, l1_capacity=256, policy="lru", l2=None, l1_ttl=30, clock=time.monotonic):
        if policy == "lru":
            self.l1 = LRUCache(l1_capacity)
        elif policy == "lfu":
            self.l1 = LFUCache(l1_capacity)
        else:
            raise ValueError("policy must be 'lru' or 'lfu'")
        self.policy = policy
        self.l2 = l2
        self.l1_ttl = l1_ttl  # seconds, or None for no expiry
        self._clock = clock
        self._lock = threading.Lock()
        self._versions = {}  # key -> number of times it was invalidated     (B)
        self._loading = {}   # key -> Event, set when the first loader is done (C)
        self.events = deque(maxlen=300)  # recent cache events for the dashboard log
        self._next_seq = 1
        self.reset_stats()

    # ---- read path -------------------------------------------------------
    def lookup(self, key, loader):
        """
        Returns (value, source, steps).
          source: which tier answered — "l1", "l2" or "db"
          steps:  each tier checked, with its result and time in ms
        """
        start = time.perf_counter()
        steps = []

        t = time.perf_counter()
        value = self._get_l1(key)
        if value is not None:
            steps.append({"tier": "l1", "op": "get", "result": "hit", "ms": _ms_since(t)})
            return self._done(key, value, "l1", steps, start)
        steps.append({"tier": "l1", "op": "get", "result": "miss", "ms": _ms_since(t)})

        if self.l2 is not None:
            t = time.perf_counter()
            value = self.l2.get(key)
            if value is not None:
                steps.append({"tier": "l2", "op": "get", "result": "hit", "ms": _ms_since(t)})
                t = time.perf_counter()
                self._put_l1(key, value)
                steps.append({"tier": "l1", "op": "promote", "result": "write", "ms": _ms_since(t)})
                return self._done(key, value, "l2", steps, start)
            steps.append({"tier": "l2", "op": "get", "result": "miss", "ms": _ms_since(t)})

        # (C) Single-flight: is another request already loading this key?
        with self._lock:
            loading = self._loading.get(key)
            first = loading is None
            if first:
                loading = self._loading[key] = threading.Event()

        if not first:
            t = time.perf_counter()
            loading.wait(timeout=10)
            value = self._get_l1(key)
            if value is not None:
                steps.append({"tier": "db", "op": "wait for same query", "result": "shared result",
                              "ms": _ms_since(t)})
                return self._done(key, value, "l1", steps, start)
            # The first request failed or discarded its result: load it ourselves.
            return self._load(key, loader, steps, start)

        try:
            return self._load(key, loader, steps, start)
        finally:
            with self._lock:
                del self._loading[key]
            loading.set()  # wake up everyone waiting for this key

    def _load(self, key, loader, steps, start):
        with self._lock:
            version = self._versions.get(key, 0)  # (B) remember the version we started with

        t = time.perf_counter()
        value = loader()
        steps.append({"tier": "db", "op": "query", "result": "found" if value is not None else "not found",
                      "ms": _ms_since(t)})
        if value is None:
            return self._done(key, value, "db", steps, start)

        if self.l2 is not None:
            t = time.perf_counter()
            self.l2.put(key, value)
            steps.append({"tier": "l2", "op": "fill", "result": "write", "ms": _ms_since(t)})
        t = time.perf_counter()
        self._put_l1(key, value)
        steps.append({"tier": "l1", "op": "fill", "result": "write", "ms": _ms_since(t)})

        # (B) A write happened while we were querying: our result may be old, so undo the save.
        with self._lock:
            changed = self._versions.get(key, 0) != version
        if changed:
            self._delete_everywhere(key)
            steps.append({"tier": "db", "op": "undo fill", "result": "data changed during query", "ms": 0})
            self._log("stale_skip", key, "db", detail="write happened during query; result not cached")
        return self._done(key, value, "db", steps, start)

    def get(self, key, loader):
        return self.lookup(key, loader)[0]

    # ---- L1 with expiry (A) -----------------------------------------------
    def _get_l1(self, key):
        entry = self.l1.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and self._clock() >= expires_at:
            self.l1.delete(key)
            self._log("expire", key, "l1", detail=f"older than {self.l1_ttl}s")
            return None
        return value

    def _put_l1(self, key, value):
        expires_at = self._clock() + self.l1_ttl if self.l1_ttl else None
        evicted = self.l1.put(key, (value, expires_at))
        if evicted is not None:
            with self._lock:
                self.evictions += 1
            self._log("evict", evicted, "l1", detail=f"{self.policy.upper()} evicted to make room")

    def _done(self, key, value, source, steps, start):
        total = _ms_since(start)
        with self._lock:
            self.hits[source] += 1
            self.latencies[source].append(total)
        self._log("hit" if source != "db" else "load", key, source, ms=total)
        return value, source, steps

    # ---- write path ------------------------------------------------------
    def invalidate(self, *keys):
        """Call AFTER the database write has committed."""
        with self._lock:
            for key in keys:
                self._versions[key] = self._versions.get(key, 0) + 1  # (B)
            self.invalidations += len(keys)
        for key in keys:
            self._delete_everywhere(key)
        self._log("invalidate", keys[0] if len(keys) == 1 else f"{len(keys)} keys", "all")

    def _delete_everywhere(self, key):
        self.l1.delete(key)
        if self.l2 is not None:
            self.l2.delete(key)

    def clear(self):
        self.l1.clear()
        self.reset_stats()
        self._log("clear", None, "l1", detail="L1 cleared and stats reset")

    # ---- stats & event log ---------------------------------------------
    def reset_stats(self):
        with self._lock:
            self.hits = {"l1": 0, "l2": 0, "db": 0}
            # Keep only the latest 2000 timings per tier.
            self.latencies = {tier: deque(maxlen=2000) for tier in self.hits}
            self.invalidations = 0
            self.evictions = 0

    def _log(self, kind, key, tier, ms=None, detail=None):
        with self._lock:
            self.events.append({"seq": self._next_seq, "ts": time.time(), "kind": kind,
                                "key": key, "tier": tier, "ms": ms, "detail": detail})
            self._next_seq += 1

    def events_after(self, seq):
        with self._lock:
            if seq >= self._next_seq:  # client saw a previous server run; send everything
                seq = 0
            return [e for e in self.events if e["seq"] > seq]

    def stats(self):
        with self._lock:
            hits = dict(self.hits)
            lat = {tier: list(v) for tier, v in self.latencies.items()}
            invalidations, evictions = self.invalidations, self.evictions
        total = sum(hits.values())
        return {
            "policy": self.policy,
            "requests": total,
            "hits": hits,
            "hit_ratio": round((hits["l1"] + hits["l2"]) / total, 4) if total else 0.0,
            "latency_ms": {tier: {"avg": round(sum(v) / len(v), 4) if v else None,
                                  "p50": _percentile(v, 50), "p95": _percentile(v, 95)}
                           for tier, v in lat.items()},
            "invalidations": invalidations,
            "evictions": evictions,
            "l1": {"size": len(self.l1), "capacity": self.l1.capacity, "ttl": self.l1_ttl},
            "l2": None if self.l2 is None else {"keys": self.l2.size(), "ttl": self.l2.ttl},
        }
