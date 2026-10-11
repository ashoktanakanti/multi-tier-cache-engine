"""
Data access layer — the only module that talks to the database.

Plain SQL (no ORM), so every query is visible. The database is the source of
truth: the cache only ever holds copies of what was read from here.
"""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.environ.get("PORTFOLIO_DB", str(Path(__file__).resolve().parent.parent / "data" / "portfolio.db"))


class InvalidRequest(ValueError):
    """A request that breaks a business rule (unknown ticker, overselling, ...)."""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


# ---- reads ---------------------------------------------------------------
def list_accounts(limit=50, offset=0):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT a.account_id, a.account_name, a.client_name,
                   COUNT(h.security_id) AS positions
            FROM accounts a
            LEFT JOIN holdings h ON h.account_id = a.account_id
            GROUP BY a.account_id
            ORDER BY a.account_id
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]


def get_account(account_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
        return dict(row) if row else None


def get_security(ticker):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM securities WHERE ticker = ?", (ticker.upper(),)).fetchone()
        return dict(row) if row else None


def search_securities(prefix, limit=10):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.ticker, s.name, s.sector,
                   (SELECT close FROM prices p WHERE p.security_id = s.security_id
                    ORDER BY price_date DESC LIMIT 1) AS last_close
            FROM securities s
            WHERE s.ticker LIKE ?
            ORDER BY s.ticker
            LIMIT ?
            """,
            (prefix.upper() + "%", limit),
        ).fetchall()
        return [dict(r) for r in rows]


def latest_close(security_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT close FROM prices WHERE security_id = ? ORDER BY price_date DESC LIMIT 1",
            (security_id,),
        ).fetchone()
        return row["close"] if row else None


def latest_price_date():
    with get_conn() as conn:
        return conn.execute("SELECT MAX(price_date) FROM prices").fetchone()[0]


def get_positions(account_id):
    """Every holding in the account with its security details and latest closing price."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.ticker, s.name, s.sector, s.asset_class, h.quantity, h.cost_basis,
                   (SELECT p.close FROM prices p
                    WHERE p.security_id = h.security_id
                    ORDER BY p.price_date DESC LIMIT 1) AS last_close
            FROM holdings h
            JOIN securities s ON s.security_id = h.security_id
            WHERE h.account_id = ?
            """,
            (account_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_value_history(account_id, since):
    """
    Daily total value of the account's current holdings since `since`.
    This joins holdings x ~250 days of prices — the expensive part.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.price_date, SUM(h.quantity * p.close) AS value
            FROM holdings h
            JOIN prices p ON p.security_id = h.security_id
            WHERE h.account_id = ? AND p.price_date >= ?
            GROUP BY p.price_date
            ORDER BY p.price_date
            """,
            (account_id, since),
        ).fetchall()
        return [(r["price_date"], r["value"]) for r in rows]


def accounts_holding(security_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT account_id FROM holdings WHERE security_id = ?", (security_id,)
        ).fetchall()
        return [r["account_id"] for r in rows]


def recent_trades(account_id, limit=20):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.trade_id, s.ticker, t.side, t.quantity, t.price, t.executed_at
            FROM trades t JOIN securities s ON s.security_id = t.security_id
            WHERE t.account_id = ?
            ORDER BY t.trade_id DESC
            LIMIT ?
            """,
            (account_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


# ---- writes --------------------------------------------------------------
def record_trade(account_id, security_id, side, quantity, price):
    """Update the holding and log the trade in ONE transaction. Returns trade_id."""
    with get_conn() as conn:
        with conn:  # commits on success, rolls back on any exception
            row = conn.execute(
                "SELECT quantity, cost_basis FROM holdings WHERE account_id = ? AND security_id = ?",
                (account_id, security_id),
            ).fetchone()
            held = row["quantity"] if row else 0

            if side == "BUY":
                new_qty = held + quantity
                # weighted average cost of old + new shares
                old_cost = held * row["cost_basis"] if row else 0
                new_cost_basis = (old_cost + quantity * price) / new_qty
                conn.execute(
                    """
                    INSERT INTO holdings (account_id, security_id, quantity, cost_basis)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (account_id, security_id)
                    DO UPDATE SET quantity = excluded.quantity, cost_basis = excluded.cost_basis
                    """,
                    (account_id, security_id, new_qty, new_cost_basis),
                )
            else:  # SELL
                if quantity > held:
                    raise InvalidRequest(f"cannot sell {quantity:g}, account holds {held:g}")
                if quantity == held:
                    conn.execute("DELETE FROM holdings WHERE account_id = ? AND security_id = ?",
                                 (account_id, security_id))
                else:
                    conn.execute("UPDATE holdings SET quantity = ? WHERE account_id = ? AND security_id = ?",
                                 (held - quantity, account_id, security_id))

            cur = conn.execute(
                "INSERT INTO trades (account_id, security_id, side, quantity, price) VALUES (?, ?, ?, ?, ?)",
                (account_id, security_id, side, quantity, price),
            )
            return cur.lastrowid


def update_latest_price(security_id, close):
    """Correct the most recent closing price of a security (e.g. a late price feed)."""
    with get_conn() as conn:
        with conn:
            conn.execute(
                """
                UPDATE prices SET close = ?
                WHERE security_id = ?
                  AND price_date = (SELECT MAX(price_date) FROM prices WHERE security_id = ?)
                """,
                (close, security_id, security_id),
            )
