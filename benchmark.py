"""
Benchmark: is the cache worth it?

Runs the real PortfolioService on a COPY of the database (so benchmark
trades don't change your data) with three traffic patterns:

  popular   Zipf: a few accounts get most of the traffic (realistic dashboards)
  random    Uniform: every account equally likely (nothing is "hot")
  writes    Zipf, but 50% of operations are trades (lots of invalidation)

and three setups: no cache, L1 LRU, L1 LFU (L1 capacity 64 of 500 accounts).
Each cached setup is warmed up first, so we measure a running service.

    python benchmark.py
"""
import json
import random
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

from cache_engine import TieredCache
from portfolio import db
from portfolio.service import PortfolioService

OPERATIONS = 1000
L1_CAPACITY = 64
PATTERNS = {"popular": (True, 0.0), "random": (False, 0.0), "writes": (True, 0.5)}  # (zipf?, write share)
RESULTS_FILE = Path(__file__).resolve().parent / "data" / "benchmark_results.json"


def make_operations(pattern, account_ids, seed):
    zipf, write_share = PATTERNS[pattern]
    rng = random.Random(seed)
    weights = [1 / rank ** 1.1 for rank in range(1, len(account_ids) + 1)] if zipf else None
    targets = rng.choices(account_ids, weights=weights, k=OPERATIONS)
    return [("write" if rng.random() < write_share else "read", a) for a in targets]


def run(service, operations, tickers):
    read_times, db_queries = [], 0
    for op, account_id in operations:
        if op == "write":
            service.trade(account_id, tickers[account_id], "BUY", 1)
            continue
        start = time.perf_counter()
        _, source, _ = service.get_summary(account_id)
        read_times.append((time.perf_counter() - start) * 1000)
        db_queries += source in ("db", "no-cache")
    return {
        "reads": len(read_times),
        "db_queries": db_queries,
        "hit_ratio": round(1 - db_queries / len(read_times), 3),
        "avg_ms": round(sum(read_times) / len(read_times), 3),
        "p50_ms": round(sorted(read_times)[len(read_times) // 2], 4),
        "total_s": round(sum(read_times) / 1000, 2),
    }


def main():
    source_db = db.DB_PATH
    account_ids = [a["account_id"] for a in db.list_accounts(limit=200, offset=0)
                   + db.list_accounts(limit=200, offset=200) + db.list_accounts(limit=200, offset=400)]
    random.Random(1).shuffle(account_ids)  # random "popularity" ranking
    tickers = {a: db.get_positions(a)[0]["ticker"] for a in account_ids}

    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        for pattern in PATTERNS:
            results[pattern] = {}
            for setup in ("no_cache", "lru", "lfu"):
                db.DB_PATH = str(Path(tmp) / f"{pattern}_{setup}.db")
                shutil.copyfile(source_db, db.DB_PATH)

                if setup == "no_cache":
                    service = PortfolioService(cache=None)
                else:
                    service = PortfolioService(TieredCache(l1_capacity=L1_CAPACITY, policy=setup))
                    run(service, make_operations(pattern, account_ids, seed=99), tickers)  # warm-up

                r = run(service, make_operations(pattern, account_ids, seed=7), tickers)
                results[pattern][setup] = r
                print(f"{pattern:<8} {setup:<9} hit={r['hit_ratio']:6.1%}  db_queries={r['db_queries']:4d}  "
                      f"avg={r['avg_ms']:7.3f} ms  p50={r['p50_ms']:8.4f} ms")
            print()
    db.DB_PATH = source_db

    RESULTS_FILE.parent.mkdir(exist_ok=True)
    RESULTS_FILE.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "operations": OPERATIONS, "l1_capacity": L1_CAPACITY, "accounts": len(account_ids),
        "results": results,
    }, indent=2))
    print(f"Saved {RESULTS_FILE}")


if __name__ == "__main__":
    main()
