# Multi-Tier Caching System (DSA + Redis + SQL)

A small movie-catalog app that demonstrates a real caching architecture end to end:
a normalized relational database as the source of truth, a hand-built LRU cache
(pure DSA — hash map + doubly linked list) as an in-process L1 cache, and Redis
as a shared L2 cache, all wired together with the **cache-aside pattern**.

## Why this exists

Anyone can `pip install redis` and call it a caching project. The point here is
to actually justify each layer:

- **SQLite (`db.py`, `schema.sql`)** — the "attic." A normalized 3-table schema
  (movies, actors, movie_actors) with foreign keys and indexes. This is the only
  place data can be *durably* written; the cache layers are disposable.
- **`lru_cache.py`** — the DSA proof point. An LRU cache built from a `dict`
  (O(1) key lookup) plus a doubly linked list with sentinel head/tail nodes
  (O(1) move-to-front and O(1) eviction). No `OrderedDict` shortcuts.
- **`redis_cache.py`** — the actual cache DB tier. JSON-serialized values with
  a TTL on every write, so entries self-expire even without explicit invalidation.
- **`cache_service.py`** — ties them together with cache-aside: check L1 → check
  L2 (Redis) → fall back to SQL → populate both tiers on the way back up. Writes
  go through the DB and then explicitly invalidate both cache tiers.

## Architecture

```
 request
    │
    ▼
 ┌─────────────┐   miss   ┌─────────────┐   miss   ┌──────────────┐
 │  L1: LRU     │ ───────▶ │ L2: Redis    │ ───────▶ │ SQLite (DB)   │
 │ (in-process) │          │ (TTL cache)  │          │ source of truth│
 └─────────────┘ ◀─────── └─────────────┘ ◀─────── └──────────────┘
        promote on hit          populate on read
```

**Writes** (`update_rating`) go straight to SQLite, then explicitly invalidate
the key in both L1 and L2 — this is the delete-on-write strategy. It trades a
small amount of write-time work for the guarantee that nobody reads stale data
after an update (verified in the invalidation test below).

## Files

| File | Purpose |
|---|---|
| `schema.sql` | Normalized schema: movies, actors, movie_actors (M:N), indexes |
| `seed_data.py` | Populates `movies.db` with sample data |
| `db.py` | Raw-SQL data access layer (the only place that touches SQLite) |
| `lru_cache.py` | Hand-built LRU cache (hash map + doubly linked list) |
| `test_lru_cache.py` | Unit tests for eviction order, recency, invalidation |
| `redis_cache.py` | Thin Redis wrapper (get/put/invalidate with TTL) |
| `cache_service.py` | Cache-aside orchestration across L1 → L2 → DB |
| `benchmark.py` | Latency comparison: raw SQL vs Redis-only vs tiered |
| `lfu_cache.py` | Second eviction policy — frequency buckets, O(1) get/put |
| `test_lfu_cache.py` | Unit tests for LFU eviction, tie-breaking, invalidation |
| `app.py` | FastAPI service exposing the cache-aside layer over HTTP |

## Running it

```bash
pip install redis pytest fastapi uvicorn
redis-server --daemonize yes        # start a local Redis instance

python3 seed_data.py                     # build & seed movies.db
python3 -m pytest test_lru_cache.py test_lfu_cache.py -v   # DSA correctness
python3 benchmark.py                     # latency comparison across all 3 tiers

uvicorn app:app --reload --port 8000     # run the API
```

### API endpoints (once `app.py` is running)

| Method & path | What it does |
|---|---|
| `GET /movies/{id}` | Movie + cast, served through L1 (LRU) → L2 (Redis) → SQL |
| `GET /movies/genre/{genre}/top?limit=5` | Top-rated movies in a genre (deliberately uncached, for contrast) |
| `PUT /movies/{id}/rating?rating=9.9` | Updates the DB and invalidates both cache tiers |
| `GET /cache/stats` | L1/L2/DB hit counters |
| `GET /health` | Liveness + live Redis connectivity check |

### LRU vs LFU

`CacheService(policy="lru")` or `CacheService(policy="lfu")` swaps the L1
eviction algorithm without touching anything else — both implement the same
`get`/`put`/`invalidate` interface, so the rest of the stack doesn't care
which one is plugged in. Good ground for a "why did you pick LRU over LFU
here" interview answer: LRU adapts instantly to changing hot sets (recency
matters more than raw count), while LFU keeps consistently popular items
cached even through a temporary burst of unrelated traffic, at the cost of
being slower to let go of a key that *used* to be hot.

## Benchmark results (sample run, 500 requests, 80% traffic to a 5-movie hot set)

```
A. Raw SQL (no cache)          avg=0.100ms   total=50.00ms
B. Redis only                  avg=0.065ms   total=32.60ms
C. Local LRU + Redis (tiered)  avg=0.032ms   total=16.19ms

Tier C cache stats: {'l1_hits': 323, 'l2_hits': 157, 'db_hits': 20}
Tiered cache is ~3.1x faster than raw SQL, ~2.0x faster than Redis-only.
```

The tiered cache wins because most traffic is served entirely in-process
(no network hop to Redis at all) once the hot set is warm — exactly the
behavior a hand-built L1 cache in front of a shared L2 cache is meant to give you.

## Design decisions worth discussing in an interview

- **Why LRU and not LFU?** LRU is cheap (O(1)) and matches "hot set" access
  patterns like this one well. LFU (frequency-based) would need a
  min-heap or frequency-bucket structure and is worth implementing as an
  extension if access patterns are more skewed/stable over time.
- **Why cache-aside instead of write-through?** Cache-aside only populates
  the cache on read, so cold/rarely-read data never wastes cache space —
  at the cost of the first read after a miss always being slow.
- **Consistency trade-off:** invalidation is synchronous and immediate here.
  At larger scale you'd consider eventual invalidation (pub/sub cache
  invalidation messages) instead of blocking the write path.

## Possible extensions

- Load-test `app.py` with `locust` or `wrk` and compare throughput LRU vs LFU.
- Add cache stampede protection (a lock or "request coalescing") for the
  cold-start case where many requests miss the cache simultaneously.
- Fail-open behavior is already implemented in `redis_cache.py`: if Redis is
  unreachable, the service falls back to hitting SQL directly instead of
  crashing — worth calling out as a resilience decision, not an oversight.
