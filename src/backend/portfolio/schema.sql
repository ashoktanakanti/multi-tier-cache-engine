-- Portfolio custody schema: clients' accounts hold positions in securities,
-- valued daily against end-of-day (EOD) closing prices.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS holdings;
DROP TABLE IF EXISTS prices;
DROP TABLE IF EXISTS securities;
DROP TABLE IF EXISTS accounts;

CREATE TABLE accounts (
    account_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    account_name  TEXT NOT NULL,
    client_name   TEXT NOT NULL,
    base_currency TEXT NOT NULL DEFAULT 'USD',
    opened_on     TEXT NOT NULL
);

CREATE TABLE securities (
    security_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker      TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    sector      TEXT NOT NULL,
    asset_class TEXT NOT NULL CHECK (asset_class IN ('Equity', 'Fixed Income', 'ETF'))
);

-- One row per security per trading day. WITHOUT ROWID stores rows physically
-- in (security_id, price_date) order, so "latest close" and "last 252 days"
-- for one security are a single contiguous index range scan.
CREATE TABLE prices (
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    price_date  TEXT    NOT NULL,
    close       REAL    NOT NULL CHECK (close > 0),
    PRIMARY KEY (security_id, price_date)
) WITHOUT ROWID;

-- Current positions. cost_basis is the average cost per unit.
CREATE TABLE holdings (
    account_id  INTEGER NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    quantity    REAL    NOT NULL CHECK (quantity > 0),
    cost_basis  REAL    NOT NULL CHECK (cost_basis > 0),
    PRIMARY KEY (account_id, security_id)
);

-- Immutable audit trail of every trade that changed a holding.
CREATE TABLE trades (
    trade_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  INTEGER NOT NULL REFERENCES accounts(account_id),
    security_id INTEGER NOT NULL REFERENCES securities(security_id),
    side        TEXT    NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity    REAL    NOT NULL CHECK (quantity > 0),
    price       REAL    NOT NULL CHECK (price > 0),
    executed_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Reverse lookup for cache invalidation: "which accounts hold this security?"
-- An EOD price load uses it to find every portfolio whose valuation changed.
CREATE INDEX idx_holdings_security ON holdings(security_id);
CREATE INDEX idx_trades_account ON trades(account_id, executed_at);
CREATE INDEX idx_prices_date ON prices(price_date);
