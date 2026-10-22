# Multi-Tier Cache Engine

A three-tier cache in front of a portfolio valuation API. The tiers are an in-process LRU or LFU cache, Redis, and SQLite. A React dashboard shows each request as it moves through them.

[![Tests](https://github.com/ashoktanakanti/multi-tier-cache-engine/actions/workflows/tests.yml/badge.svg)](https://github.com/ashoktanakanti/multi-tier-cache-engine/actions/workflows/tests.yml)

[Live demo](https://multi-tier-cache-engine.onrender.com) · [API docs](https://multi-tier-cache-engine.onrender.com/docs)

The live demo runs on Render's free plan, so it may take a while to respond after a period of inactivity.

![Dashboard overview](docs/screenshots/overview.png)

## What it does

The demo data has 500 accounts and 1,500 securities. `GET /accounts/{id}/summary` returns a portfolio summary: market value, profit and loss, sector weights, top holdings, and 1-year return, volatility and max drawdown computed from a year of daily values.

Building that summary means joining holdings to prices and reading a year of history. Without a cache, the median read took about 36 ms in the benchmark run described below. The cache keeps finished summaries so repeated reads skip that work.

Reads go down the tiers in order. A miss in one tier falls through to the next. A value found in a lower tier is copied back up.

| Tier | Implementation | Median read in the benchmark |
|---|---|---|
| L1 | In-process LRU or LFU cache, written from scratch. Thread-safe. Entries expire after 30 s by default. | 0.012 ms (LRU), 0.013 ms (LFU) |
| L2 | Redis with JSON values and a 5-minute TTL. Calls time out after 50 ms. | Not measured |
| L3 | SQLite. This is the source of truth. | About 36 ms |

Writes go to the database first. After the commit, the cached summaries for the affected accounts are deleted from L1 and L2. The next read rebuilds them. The cache never updates a value in place.

## Using the dashboard

The **Playground** on the Overview page has four tabs. Every timing comes from a real request to the server.

**Read key.** Enter an account ID from 1 to 500 and click **Read key**. The first read misses every cache and runs the database query, then stores the result in L2 and L1. Click **Read again** to see an L1 hit.

![Read: cache miss](docs/screenshots/read-miss.png)

![Read: cache hit](docs/screenshots/read-hit.png)

**Write.** Buy or sell shares for an account. The trade and its holding update run in one transaction. Selling more shares than the account holds is rejected, and nothing changes. After a successful trade, the summary for that account is deleted from L1 and L2. **Trace next read** shows the following read going back to the database.

![Write: trade and invalidate](docs/screenshots/write.png)

**Price.** Change a stock's price. Every account that holds the stock has its cached summary deleted. Accounts that don't hold it stay cached.

![Price update](docs/screenshots/price.png)

**Stats.** Generate 100, 300 or 1,000 requests, either Zipf-distributed (a few accounts receive most of the traffic) or uniform (every account is equally likely). The traffic is generated in the browser and sent to the real API.

![Stats: traffic generator](docs/screenshots/stats.png)

Other pages:

- **Overview:** totals for requests, hit ratio and latency, the tier view, and the engine log.
- **Accounts:** all 500 accounts. Accounts currently in L1 are marked.
- **Benchmark:** the results in `src/backend/data/benchmark_results.json`.
- **Design notes:** the reasoning behind the design.

![Accounts page](docs/screenshots/accounts.png)

### Engine log

Each line is one cache event:

- **HIT:** a request was served from a tier.
- **MISS:** the value was read from the database and then stored.
- **EVICT:** the LRU or LFU policy removed an entry to make room.
- **EXPIRE:** an L1 entry passed its TTL and was removed.
- **INVAL:** a write deleted the cached copy.
- **GUARD:** a write happened while a read was running, so that read's result was not cached.

## Benchmark

`src/backend/benchmark.py` runs 1,000 operations over the 500 accounts, with an L1 capacity of 64. It runs each traffic pattern with no cache, with L1 LRU, and with L1 LFU. Each cached setup gets a warm-up run first. The benchmark runs without L1 expiry, so its numbers don't include TTL effects.

| Traffic | Setup | Hit ratio | Database queries | Median read |
|---|---|---|---|---|
| Popular accounts (Zipf) | No cache | 0% | 1000 / 1000 | 35.97 ms |
| | L1 LRU | 68.6% | 314 / 1000 | 0.012 ms |
| | L1 LFU | 74.3% | 257 / 1000 | 0.013 ms |
| Random accounts (uniform) | No cache | 0% | 1000 / 1000 | 20.75 ms |
| | L1 LRU | 12.9% | 871 / 1000 | 19.70 ms |
| | L1 LFU | 12.6% | 874 / 1000 | 19.11 ms |
| Popular accounts, half trades | No cache | 0% | 507 / 507 | 22.79 ms |
| | L1 LRU | 37.5% | 317 / 507 | 14.99 ms |
| | L1 LFU | 37.5% | 317 / 507 | 15.20 ms |

What the numbers show:

- With popular accounts, the cache answered 68.6% of reads with LRU and 74.3% with LFU. Those reads never reached the database.
- LFU had the higher hit ratio on popular traffic. Its frequency counts keep frequently used accounts from being pushed out by one-off reads.
- With random traffic, only 64 of 500 accounts fit in L1, so the hit ratio stayed around 13%.
- In the random run, the average read was slower with LRU (33.2 ms) than with no cache (20.9 ms), even though the medians were close. The benchmark script does not explain the higher average.
- Trades invalidate cached summaries, so the write-heavy run had a lower hit ratio, 37.5%.

The hit ratios and query counts come from fixed random seeds, so they should repeat on another machine. Timings depend on the machine.

## Build, test and run locally

Python 3.12 and Node.js 22 are what CI and the Docker image use.

```bash
# Python setup
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Tests (from the repo root; expect 51 passed)
pytest

# Create the demo database, from src/backend
cd src/backend
python -m portfolio.seed

# Start the API with an in-memory fake Redis (no Redis server needed)
#   PowerShell:   $env:REDIS_URL="memory://"
#   macOS/Linux:  export REDIS_URL=memory://
uvicorn portfolio.api:app --port 8000

# In a second terminal, start the dashboard
cd src/frontend
npm install
npm run dev                          # http://localhost:5173
```

The Vite dev server forwards `/api` to `http://localhost:8000`. Set `API_URL` to point it elsewhere.

Settings are read from environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `REDIS_URL` | not set | `memory://` for the in-memory fake, `redis://...` for a real Redis, or unset for L1 only |
| `CACHE_POLICY` | `lru` | `lru` or `lfu` |
| `L1_CAPACITY` | `256` | Maximum number of entries in L1 |
| `L1_TTL` | `30` | Seconds before an L1 entry expires |
| `PORTFOLIO_DB` | `src/backend/data/portfolio.db` | Path to the SQLite database |

To reset the demo data, run `python -m portfolio.seed` again from `src/backend` and restart the API. To rerun the benchmark, run `python benchmark.py` from `src/backend`.

## Deploy on Render

`render.yaml` defines one web service on the free plan, using the Docker runtime. It sets `REDIS_URL=memory://`, `CACHE_POLICY=lru`, and a health check at `/health`.

The Docker build compiles the React app, copies it into the image, and creates the demo database. The file declares no persistent disk, so trades and price changes made on the live server are lost when the service restarts.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/accounts/{id}/summary` | Account summary through the cache. The `X-Cache` response header is `L1`, `L2` or `DB`. Add `?use_cache=false` to skip the cache. |
| GET | `/cache/lookup/{id}` | The same read, plus each step and its timing |
| GET | `/accounts/{id}/trades` | Recent trades for an account |
| POST | `/accounts/{id}/trades` | Buy or sell. Body: `{"ticker": "...", "side": "BUY", "quantity": 100}` |
| PUT | `/securities/{ticker}/price` | Set a price. Body: `{"close": 700}` |
| GET | `/cache/stats` | Hits per tier, hit ratio, latency percentiles and cache sizes |
| GET | `/cache/events?after=N` | Cache events after sequence number N |
| DELETE | `/cache` | Empty L1 and reset the counters |
| GET | `/accounts`, `/securities?q=`, `/benchmark`, `/health` | Supporting endpoints |

## Design decisions

- **Two cache tiers.** L1 is fastest, but each server process has its own. L2 (Redis) is shared between processes and keeps its entries across application restarts.
- **LRU and LFU.** LRU evicts the least recently used entry. LFU evicts the least frequently used one. Both are built from a hash map plus an ordering structure, so lookups don't scan the cache. The policy is chosen with `CACHE_POLICY`.
- **Cache-aside.** The cache is filled only when a read asks for a value. Accounts nobody reads take no cache space.
- **Delete on write.** After a change, the cached copy is deleted, not edited. The next read rebuilds it from the database.
- **Expiry.** L1 entries expire after 30 s by default. Redis entries expire after 5 minutes.
- **Fail-open.** Redis errors are treated as misses, so the request falls through to the database. Redis calls time out after 50 ms, so a hung Redis can't be slower than the database.
- **Locking.** Each cache takes a lock around its operations, because the server handles requests on several threads.
- **Transactions.** A trade updates the holding and records the trade in one transaction, so both happen or neither does.

**When caching is not worth it:** data that changes on almost every read, access spread across far more data than the cache can hold, or queries that are already fast.

### Three problems the cache has to handle

Each problem below has a test in `tests/test_tiered.py`.

| Problem | What goes wrong | How it's handled |
|---|---|---|
| Stale copies on other servers | A write clears the cache on the server that handled it. Another server can still hold the old summary in its L1. | L1 entries expire, so a stale copy lasts at most `L1_TTL` seconds. Test: `test_other_servers_stale_copy_lasts_at_most_the_ttl`. |
| Read/write race | A read starts, a write commits and clears the cache, then the slow read finishes and stores its old result. | Each key has a version number that every invalidation increments. A read that sees the version change removes its own result. Test: `test_write_during_a_slow_read_is_not_cached`. |
| Cache stampede | Many requests miss the same key at once, and each runs the same database query. | Single-flight: the first request runs the query, and the others wait for its result. Test: `test_many_misses_on_one_key_run_one_query`. |

### Known limitations

- **The live demo's L2 is not shared.** It runs one server with an in-memory fake Redis, so L2 behaves like a second, in-process cache there. L2 is useful with several servers and a real Redis. Set `REDIS_URL` to a real Redis to try that.
- **Stale copies can last up to the TTL.** With the default `L1_TTL` of 30 s, another server can show old data for that long. Broadcasting invalidations over Redis pub/sub would remove the delay.
- **LFU counts never decay.** An account that was popular long ago can keep its place in the cache. Aging the counts over time would fix this.

## Project layout

```
src/
├── backend/
│   ├── cache_engine/        The cache. Knows nothing about portfolios.
│   │   ├── lru.py           LRU cache
│   │   ├── lfu.py           LFU cache
│   │   ├── redis_tier.py    Redis (L2)
│   │   └── tiered.py        L1 → L2 → L3 lookup, invalidation, stats, event log
│   ├── portfolio/           The portfolio application that uses the cache
│   │   ├── schema.sql       Database tables
│   │   ├── seed.py          Generates the demo data
│   │   ├── db.py            SQL queries
│   │   ├── service.py       Summaries, trades, price updates
│   │   └── api.py           FastAPI routes
│   ├── benchmark.py         The benchmark above
│   └── data/                Benchmark results (the database is generated, not committed)
└── frontend/                React dashboard (Vite, Tailwind CSS)
tests/                       pytest suite (51 tests)
docs/screenshots/            Images used in this README
Dockerfile, render.yaml      Render deployment
```
