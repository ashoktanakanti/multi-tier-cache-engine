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
    def __init__(self, l1_capacity=256, policy="lru", l2=None):
        if policy == "lru":
            self.l1 = LRUCache(l1_capacity)
        elif policy == "lfu":
            self.l1 = LFUCache(l1_capacity)
        else:
            raise ValueError("policy must be 'lru' or 'lfu'")
        self.policy = policy
        self.l2 = l2
        self._lock = threading.Lock()
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
        value = self.l1.get(key)
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

        t = time.perf_counter()
        value = loader()
        steps.append({"tier": "db", "op": "query", "result": "found" if value is not None else "not found",
                      "ms": _ms_since(t)})
        if value is not None:
            if self.l2 is not None:
                t = time.perf_counter()
                self.l2.put(key, value)
                steps.append({"tier": "l2", "op": "fill", "result": "write", "ms": _ms_since(t)})
            t = time.perf_counter()
            self._put_l1(key, value)
            steps.append({"tier": "l1", "op": "fill", "result": "write", "ms": _ms_since(t)})
        return self._done(key, value, "db", steps, start)

    def get(self, key, loader):
        return self.lookup(key, loader)[0]

    def _put_l1(self, key, value):
        evicted = self.l1.put(key, value)
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
        for key in keys:
            self.l1.delete(key)
            if self.l2 is not None:
                self.l2.delete(key)
        with self._lock:
            self.invalidations += len(keys)
        self._log("invalidate", keys[0] if len(keys) == 1 else f"{len(keys)} keys", "all")

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
            "l1": {"size": len(self.l1), "capacity": self.l1.capacity},
            "l2": None if self.l2 is None else {"keys": self.l2.size(), "ttl": self.l2.ttl},
        }
