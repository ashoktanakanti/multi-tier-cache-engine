"""
PortfolioService — business logic, and the reason the cache exists.

An account summary (what a client dashboard shows) needs:
  - every holding joined to its latest price   -> market value, profit/loss
  - a breakdown by sector and the top holdings
  - one year of daily values (holdings x ~250 days) -> returns, volatility

Why it's worth caching:
  1. Expensive: ~25 ms of SQL + maths, versus a few microseconds from L1.
  2. Read-heavy: dashboards re-read the same accounts all day.
  3. Changes rarely and at known moments: only when the account trades or a
     price is updated. Both go through this service, so we know exactly
     which cache keys to invalidate.
"""
import math
import time
from datetime import date, timedelta

from . import db


def summary_key(account_id):
    return f"portfolio:summary:{account_id}"


class AccountNotFound(LookupError):
    pass


class PortfolioService:
    def __init__(self, cache):
        self.cache = cache  # a TieredCache, or None to always hit the database

    # ---- reads -----------------------------------------------------------
    def get_summary(self, account_id, use_cache=True):
        """Returns (summary, source, steps). source is l1 | l2 | db | no-cache."""
        if self.cache is None or not use_cache:
            return compute_summary(account_id), "no-cache", []
        return self.cache.lookup(summary_key(account_id), lambda: compute_summary(account_id))

    # ---- writes: update the DB first, then invalidate ------------------------
    def trade(self, account_id, ticker, side, quantity, price=None):
        if db.get_account(account_id) is None:
            raise AccountNotFound(account_id)
        security = db.get_security(ticker)
        if security is None:
            raise db.InvalidRequest(f"unknown ticker {ticker!r}")
        price = price or db.latest_close(security["security_id"])

        start = time.perf_counter()
        trade_id = db.record_trade(account_id, security["security_id"], side, quantity, price)
        db_ms = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        if self.cache is not None:
            self.cache.invalidate(summary_key(account_id))
        invalidate_ms = (time.perf_counter() - start) * 1000

        return {"trade_id": trade_id, "account_id": account_id, "ticker": security["ticker"],
                "side": side, "quantity": quantity, "price": price,
                "invalidated": [summary_key(account_id)],
                "db_ms": round(db_ms, 3), "invalidate_ms": round(invalidate_ms, 3)}

    def update_price(self, ticker, close):
        security = db.get_security(ticker)
        if security is None:
            raise db.InvalidRequest(f"unknown ticker {ticker!r}")

        start = time.perf_counter()
        db.update_latest_price(security["security_id"], close)
        db_ms = (time.perf_counter() - start) * 1000

        # One price affects every account that holds this security.
        start = time.perf_counter()
        affected = db.accounts_holding(security["security_id"])
        if self.cache is not None and affected:
            self.cache.invalidate(*[summary_key(a) for a in affected])
        invalidate_ms = (time.perf_counter() - start) * 1000

        return {"ticker": security["ticker"], "close": close, "accounts_invalidated": len(affected),
                "db_ms": round(db_ms, 3), "invalidate_ms": round(invalidate_ms, 3)}


# ---- the expensive computation (knows nothing about caching) -----------------
def compute_summary(account_id):
    account = db.get_account(account_id)
    if account is None:
        return None

    positions = db.get_positions(account_id)
    as_of = db.latest_price_date()
    one_year_ago = (date.fromisoformat(as_of) - timedelta(days=365)).isoformat()
    history = db.get_value_history(account_id, one_year_ago)

    total_value = total_cost = 0.0
    sectors = {}
    holdings = []
    for p in positions:
        value = p["quantity"] * p["last_close"]
        cost = p["quantity"] * p["cost_basis"]
        total_value += value
        total_cost += cost
        sectors[p["sector"]] = sectors.get(p["sector"], 0) + value
        holdings.append({"ticker": p["ticker"], "name": p["name"], "sector": p["sector"],
                         "quantity": p["quantity"], "last_close": round(p["last_close"], 2),
                         "market_value": round(value, 2), "profit_loss": round(value - cost, 2)})
    holdings.sort(key=lambda h: h["market_value"], reverse=True)

    return {
        "account": account,
        "as_of": as_of,
        "positions": len(positions),
        "market_value": round(total_value, 2),
        "profit_loss": round(total_value - total_cost, 2),
        "profit_loss_pct": round((total_value - total_cost) / total_cost, 4) if total_cost else 0,
        "sectors": sorted(({"sector": s, "weight": round(v / total_value, 4)} for s, v in sectors.items()),
                          key=lambda s: s["weight"], reverse=True),
        "top_holdings": holdings[:10],
        "performance": performance(history),
        "history": [{"date": d, "value": round(v, 2)} for d, v in history],
    }


def performance(history):
    """1-year return, annualised volatility and max drawdown from daily values."""
    values = [v for _, v in history]
    if len(values) < 3:
        return {"return_1y": None, "volatility": None, "max_drawdown": None}

    daily_returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)

    peak, max_drawdown = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        max_drawdown = min(max_drawdown, v / peak - 1)

    return {
        "return_1y": round(values[-1] / values[0] - 1, 4),
        "volatility": round(math.sqrt(variance) * math.sqrt(252), 4),
        "max_drawdown": round(max_drawdown, 4),
    }
