"""
REST API (FastAPI).

  GET    /health                       is the API up, is Redis connected
  GET    /accounts                     list accounts (cheap query, not cached)
  GET    /accounts/{id}/summary        account summary — CACHED (L1 -> L2 -> DB)
                                       ?use_cache=false skips the cache, for comparison
  GET    /accounts/{id}/trades         recent trades
  POST   /accounts/{id}/trades         buy/sell -> invalidates that account's summary
  PUT    /securities/{ticker}/price    correct a price -> invalidates every holder
  GET    /securities?q=AB              ticker search
  GET    /cache/lookup/{id}            summary read + the step-by-step path through the tiers
  GET    /cache/stats                  hits per tier, hit ratio, latencies, sizes
  GET    /cache/events?after=N         recent cache events (for the live log)
  DELETE /cache                        clear L1 and reset stats
  GET    /benchmark                    results written by benchmark.py

Summary responses include an X-Cache header (L1 / L2 / DB) showing which tier answered.

Settings (environment variables):
  REDIS_URL     redis://localhost:6379/0, or memory:// for a fake in-memory Redis.
                Not set = no L2.
  CACHE_POLICY  lru (default) or lfu
  L1_CAPACITY   default 256

Run:  uvicorn portfolio.api:app --reload --port 8000
"""
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from cache_engine import RedisTier, TieredCache

from . import db
from .service import AccountNotFound, PortfolioService, summary_key

BENCHMARK_FILE = Path(__file__).resolve().parent.parent / "data" / "benchmark_results.json"


def create_service():
    redis_url = os.environ.get("REDIS_URL")
    l2 = RedisTier.from_url(redis_url) if redis_url else None
    cache = TieredCache(
        l1_capacity=int(os.environ.get("L1_CAPACITY", 256)),
        policy=os.environ.get("CACHE_POLICY", "lru"),
        l2=l2,
    )
    return PortfolioService(cache)


@asynccontextmanager
async def lifespan(app):
    if not Path(db.DB_PATH).exists():
        raise RuntimeError(f"{db.DB_PATH} not found. Run: python -m portfolio.seed")
    app.state.service = create_service()
    yield


app = FastAPI(title="Portfolio Valuation API", version="2.0", lifespan=lifespan)


def service() -> PortfolioService:
    return app.state.service


class TradeIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    side: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0)
    price: float | None = Field(default=None, gt=0)


class PriceIn(BaseModel):
    close: float = Field(gt=0)


@app.get("/health")
def health():
    cache = service().cache
    if cache.l2 is None:
        redis_status = "disabled"
    elif os.environ.get("REDIS_URL") == "memory://":
        redis_status = "in-memory fake"
    else:
        redis_status = "connected" if cache.l2.ping() else "down"
    return {"status": "ok", "policy": cache.policy, "redis": redis_status}


@app.get("/accounts")
def list_accounts(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    accounts = db.list_accounts(limit, offset)
    for a in accounts:
        a["cached"] = summary_key(a["account_id"]) in service().cache.l1
    return accounts


@app.get("/accounts/{account_id}/summary")
def account_summary(account_id: int, response: Response, use_cache: bool = True):
    start = time.perf_counter()
    summary, source, _ = service().get_summary(account_id, use_cache)
    response.headers["X-Cache"] = source.upper()
    response.headers["X-Response-Time-ms"] = f"{(time.perf_counter() - start) * 1000:.3f}"
    if summary is None:
        raise HTTPException(404, "Account not found")
    return summary


@app.get("/accounts/{account_id}/trades")
def account_trades(account_id: int):
    if db.get_account(account_id) is None:
        raise HTTPException(404, "Account not found")
    return db.recent_trades(account_id)


@app.post("/accounts/{account_id}/trades", status_code=201)
def create_trade(account_id: int, body: TradeIn):
    try:
        return service().trade(account_id, body.ticker, body.side, body.quantity, body.price)
    except AccountNotFound:
        raise HTTPException(404, "Account not found")
    except db.InvalidRequest as e:
        raise HTTPException(422, str(e))


@app.get("/securities")
def search_securities(q: str = ""):
    return db.search_securities(q)


@app.put("/securities/{ticker}/price")
def update_price(ticker: str, body: PriceIn):
    try:
        return service().update_price(ticker, body.close)
    except db.InvalidRequest as e:
        raise HTTPException(404, str(e))


@app.get("/cache/lookup/{account_id}")
def traced_lookup(account_id: int):
    start = time.perf_counter()
    summary, source, steps = service().get_summary(account_id)
    total_ms = (time.perf_counter() - start) * 1000
    if summary is None:
        raise HTTPException(404, "Account not found")
    return {
        "key": summary_key(account_id),
        "source": source,
        "total_ms": round(total_ms, 4),
        "steps": steps,
        "summary": {k: summary[k] for k in ("account", "as_of", "positions", "market_value",
                                            "profit_loss", "profit_loss_pct", "performance")}
                   | {"top_holdings": summary["top_holdings"][:5]},
    }


@app.get("/cache/stats")
def cache_stats():
    stats = service().cache.stats()
    stats["db_size_bytes"] = Path(db.DB_PATH).stat().st_size
    return stats


@app.get("/cache/events")
def cache_events(after: int = 0):
    return service().cache.events_after(after)


@app.delete("/cache", status_code=204)
def clear_cache():
    service().cache.clear()


@app.get("/benchmark")
def benchmark_results():
    if not BENCHMARK_FILE.exists():
        raise HTTPException(404, "No results yet. Run: python benchmark.py")
    return json.loads(BENCHMARK_FILE.read_text())


# In production (Render) the built React app is served from the same server.
# Registered last, so every API route above takes priority over static files.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
