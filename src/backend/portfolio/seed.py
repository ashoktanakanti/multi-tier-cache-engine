"""
Builds a realistic-sized portfolio database from schema.sql.

Defaults: 1,500 securities x 1 year of daily closes (~390k price rows) and
500 client accounts holding 20-120 positions each. That size matters: with a
toy dataset every query takes microseconds and a cache can't be justified.
The generator is seeded, so every run produces the same data.

    python -m portfolio.seed                  # full dataset (a few seconds)
    python -m portfolio.seed --small          # tiny dataset for quick experiments
"""
from __future__ import annotations

import argparse
import math
import random
import sqlite3
import string
from datetime import date, timedelta
from pathlib import Path

from . import db

SCHEMA = Path(__file__).with_name("schema.sql")

SECTORS = [
    "Information Technology", "Financials", "Health Care", "Consumer Discretionary",
    "Industrials", "Communication Services", "Consumer Staples", "Energy",
    "Utilities", "Real Estate", "Materials",
]
NAME_PARTS = (
    ["Atlas", "Northwind", "Granite", "Blue Ridge", "Meridian", "Summit", "Harbor", "Pioneer",
     "Evergreen", "Sterling", "Beacon", "Crescent", "Keystone", "Lakeshore", "Redwood", "Silverline"],
    ["Holdings", "Systems", "Capital", "Industries", "Group", "Technologies", "Partners",
     "Resources", "Health", "Energy", "Networks", "Brands"],
)
CLIENTS = [
    "Lakeview Teachers' Pension", "Halvorsen Family Office", "St. Brigid Hospital Endowment",
    "Cedar Valley University Foundation", "Orion Sovereign Fund", "Marlowe Charitable Trust",
    "Northgate Insurance Co.", "Kestrel Municipal Retirement", "Aldridge Wealth Partners",
    "Juniper Community Foundation",
]
MANDATES = ["Global Equity", "US Large Cap", "Balanced 60/40", "Fixed Income Core",
            "Dividend Income", "Sector Rotation", "ESG Leaders", "Emerging Growth"]


def business_days(end: date, count: int) -> list[str]:
    days, d = [], end
    while len(days) < count:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d -= timedelta(days=1)
    return days[::-1]


def unique_tickers(rng: random.Random, n: int) -> list[str]:
    seen: set[str] = set()
    while len(seen) < n:
        seen.add("".join(rng.choices(string.ascii_uppercase, k=rng.choice((3, 4)))))
    return sorted(seen)


def build(path: str, n_securities=1500, n_accounts=500, n_days=260,
          positions=(20, 120), seed=42, end: date | None = None) -> dict:
    rng = random.Random(seed)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    end = end or date.today() - timedelta(days=1)
    days = business_days(end, n_days)

    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA.read_text())

    # Securities: mostly equities, some ETFs and bond funds (lower volatility).
    securities = []
    for i, ticker in enumerate(unique_tickers(rng, n_securities), start=1):
        asset_class = rng.choices(["Equity", "ETF", "Fixed Income"], weights=[80, 12, 8])[0]
        sector = "Fixed Income" if asset_class == "Fixed Income" else rng.choice(SECTORS)
        name = f"{rng.choice(NAME_PARTS[0])} {rng.choice(NAME_PARTS[1])} ({ticker})"
        securities.append((i, ticker, name, sector, asset_class))
    conn.executemany("INSERT INTO securities VALUES (?, ?, ?, ?, ?)", securities)

    # Prices: geometric random walk with per-security drift and volatility.
    price_rows = []
    for sid, _, _, _, asset_class in securities:
        vol = {"Equity": rng.uniform(0.15, 0.55), "ETF": rng.uniform(0.10, 0.25),
               "Fixed Income": rng.uniform(0.03, 0.08)}[asset_class] / math.sqrt(252)
        drift = rng.uniform(-0.05, 0.15) / 252
        price = rng.uniform(10, 400)
        for d in days:
            price *= math.exp(drift - vol * vol / 2 + vol * rng.gauss(0, 1))
            price_rows.append((sid, d, round(price, 4)))
    conn.executemany("INSERT INTO prices VALUES (?, ?, ?)", price_rows)

    # Accounts and their positions, bought at a price from the past year.
    first_close = {sid: None for sid, *_ in securities}
    for sid, d, close in price_rows:
        if first_close[sid] is None:
            first_close[sid] = close
    holdings = []
    for aid in range(1, n_accounts + 1):
        client = rng.choice(CLIENTS)
        conn.execute(
            "INSERT INTO accounts VALUES (?, ?, ?, 'USD', ?)",
            (aid, f"{client.split()[0]} {rng.choice(MANDATES)} #{aid:04d}", client, days[0]),
        )
        for sid in rng.sample(range(1, n_securities + 1), k=rng.randint(*positions)):
            qty = rng.choice([50, 100, 250, 500, 1000, 2500])
            cost = first_close[sid] * rng.uniform(0.8, 1.2)
            holdings.append((aid, sid, qty, round(cost, 4)))
    conn.executemany("INSERT INTO holdings VALUES (?, ?, ?, ?)", holdings)

    conn.commit()
    conn.execute("ANALYZE")  # give the query planner real statistics
    conn.close()
    return {"securities": n_securities, "accounts": n_accounts, "prices": len(price_rows),
            "holdings": len(holdings), "first_day": days[0], "last_day": days[-1]}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--small", action="store_true", help="tiny dataset (50 securities, 20 accounts)")
    parser.add_argument("--path", default=db.DB_PATH)
    args = parser.parse_args()
    if args.small:
        info = build(args.path, n_securities=50, n_accounts=20, n_days=60, positions=(5, 15))
    else:
        info = build(args.path)
    print(f"Seeded {args.path}: {info}")


if __name__ == "__main__":
    main()
