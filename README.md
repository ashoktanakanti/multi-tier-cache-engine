# Multi-Tier Cache Engine: Portfolio Valuation

A portfolio-valuation API (like what a custody bank shows its clients) with a
**three-tier cache** in front of the database, plus a React dashboard that
shows every cache hit, miss and invalidation live.

```
 request ──▶  L1  in-memory LRU/LFU     ~10 µs     (built from scratch: hash map + linked list)
                │ miss
                ▼
              L2  Redis                   < 1 ms    (shared by all server processes, TTL)
                │ miss
                ▼
              L3  SQLite database         ~25–45 ms (source of truth)

 On the way back up, the value is stored in L2 and L1.
 On a write (trade / price change), the DB is updated first, then the cached copy is deleted.
```

## Why cache this at all?

A cache only earns its place if the data is **expensive to compute**, **read
much more often than it changes**, and **changes at moments we control**.
An account summary meets all three:

| | |
|---|---|
| **Expensive** | Joins every holding to its latest price and adds up a year of daily values (~35k holdings × 390k price rows in the dataset). About 25–45 ms per account. |
| **Read a lot** | Dashboards and reports read the same accounts repeatedly. |
| **Changes at known moments** | Only when the account trades or a price is updated. Both go through our service, so we know exactly which keys to delete. |

When it would **not** be worth it: live tick-by-tick prices, random access
over far more keys than fit in the cache, write-heavy data, or cheap queries.
The benchmark below shows two of these cases.

## Benchmark results

`python benchmark.py`: 1,000 operations per run over 500 accounts, L1 capacity 64, warmed-up cache.

| Traffic pattern | Setup | Hit ratio | DB queries | Typical read (p50) |
|---|---|---|---|---|
| **Popular accounts** (Zipf, realistic) | no cache | 0.0% | 1000 / 1000 | 36 ms |
|  | L1 LRU | 68.6% | 314 / 1000 | **0.012 ms** |
|  | L1 LFU | 74.3% | 257 / 1000 | **0.013 ms** |
| **Random accounts** (uniform) | no cache | 0.0% | 1000 / 1000 | 21 ms |
|  | L1 LRU | 12.9% | 871 / 1000 | 20 ms |
|  | L1 LFU | 12.6% | 874 / 1000 | 19 ms |
| **50% trades** | no cache | 0.0% | 507 / 507 | 23 ms |
|  | L1 LRU | 37.5% | 317 / 507 | 15 ms |
|  | L1 LFU | 37.5% | 317 / 507 | 15 ms |

What the numbers show:
- With realistic traffic the cache removes **~70% of database queries**, and a cache hit is about **3,000× faster** than a database query.
- **LFU beats LRU** when a stable set of accounts is popular (74% vs 69%), because one-off reads can't push the popular accounts out.
- With **random access**, only 64 of 500 accounts fit in L1, so the cache barely helps.
- With **lots of writes**, every trade deletes a cached entry, so hits drop.
- Wall-clock times vary by ±50% between runs on a laptop. Hit ratio and DB query counts don't vary, so treat those as the main evidence.

## Project structure

```
cache_engine/           reusable cache library (no business logic)
  lru.py                LRU cache: dict + doubly linked list, O(1)
  lfu.py                LFU cache: frequency buckets, O(1)
  redis_tier.py         Redis wrapper: JSON + TTL, fail-open on errors
  tiered.py             cache-aside across L1 -> L2 -> DB, stats, event log
portfolio/
  schema.sql            accounts, securities, prices, holdings, trades
  seed.py               generates 500 accounts / 1,500 securities / 1 year of prices
  db.py                 all SQL lives here
  service.py            account summary + trade / price update (with invalidation)
  api.py                FastAPI REST endpoints
frontend/               React + Tailwind dashboard
tests/                  pytest: cache structures, tiers, service, API
benchmark.py            the numbers above
Dockerfile, render.yaml  one-service deployment on Render
```

## Running it

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

python -m portfolio.seed          # builds data/portfolio.db (~5 s)
pytest                            # 46 tests

# API, with a fake in-memory Redis (no Redis install needed)
set REDIS_URL=memory://           # PowerShell: $env:REDIS_URL="memory://"
uvicorn portfolio.api:app --port 8000

# dashboard (second terminal)
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

To use a real Redis, set `REDIS_URL=redis://localhost:6379/0`. Leave
`REDIS_URL` unset to run with L1 only. Use `CACHE_POLICY=lfu` to switch L1 to LFU.

## Deploying to Render

The repo includes a `Dockerfile` and a `render.yaml` blueprint. Everything runs
as **one web service**: the Docker build compiles the React app, installs the
Python API, and seeds the database; then FastAPI serves both the API and the
dashboard from the same URL.

1. On [render.com](https://render.com): **New → Blueprint**, then pick this repository.
2. Render reads `render.yaml` and creates the free web service. The first build takes a few minutes.
3. Open the service URL. The dashboard loads at `/` and the API docs at `/docs`.

Notes:
- The free plan has no Redis, so L2 uses the in-memory fake (`REDIS_URL=memory://`). For a real L2, create a Render **Key Value** instance and set `REDIS_URL` to its internal URL.
- The free plan's disk resets on every deploy or restart, so the demo database is rebuilt fresh each time. Fine for a demo.
- Free services sleep after ~15 minutes idle; the first request after that takes ~30–60 s.

## API

| Method | Path | What it does |
|---|---|---|
| GET | `/accounts/{id}/summary` | Account summary through the cache. Response header `X-Cache: L1 / L2 / DB` |
| GET | `/cache/lookup/{id}` | Same read, plus each tier it checked and how long each step took |
| POST | `/accounts/{id}/trades` | Buy/sell. Updates the DB, then invalidates that account |
| PUT | `/securities/{ticker}/price` | Price correction. Invalidates every account holding it |
| GET | `/cache/stats` | Hits per tier, hit ratio, latency, sizes |
| GET | `/cache/events` | Recent cache events (used by the live log) |
| DELETE | `/cache` | Clear L1 and reset stats |
| GET | `/accounts`, `/securities?q=`, `/benchmark`, `/health` | Supporting endpoints |

Interactive docs: http://localhost:8000/docs

## Design decisions (interview notes)

- **Why two cache tiers?** L1 is fastest (no network) but private to one server process. L2 (Redis) is shared by every process and survives restarts.
- **LRU vs LFU?** LRU adapts quickly when what's popular changes. LFU protects consistently popular keys from bursts of one-off reads. Both are O(1). The benchmark shows LFU winning on a stable popular set.
- **Cache-aside** (not write-through): the cache only stores what someone actually read, so unused accounts don't waste memory.
- **Delete on write** (not update): after a trade commits, the cached copy is deleted and the next read rebuilds it from the database, so a stale or half-updated copy can't be served.
- **TTL on Redis** (5 min): a safety net if an invalidation is ever missed.
- **Fail-open**: if Redis is down, its errors count as misses and requests go to the database. The cache makes the app faster but is never required for it to work.
- **Thread safety**: FastAPI runs requests on several threads, so each L1 operation holds a lock, and a test runs 8 threads against it.
- **Transactions**: a trade updates the holding and writes the audit row in one SQL transaction. Overselling rolls everything back.

## Possible extensions

- **Request coalescing**: if 100 requests miss the same key at once, run the database query once and share the result.
- **Redis pub/sub invalidation**: so a write on one server clears the L1 on every other server.
- A real Redis server in the benchmark to measure L2 latency over the network.
