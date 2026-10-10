import pytest

from cache_engine import TieredCache
from portfolio import db
from portfolio.service import AccountNotFound, PortfolioService, compute_summary, performance


@pytest.fixture
def service(portfolio_db, fake_redis):
    return PortfolioService(TieredCache(l2=fake_redis))


def first_holding(account_id):
    return db.get_positions(account_id)[0]


def test_summary_numbers_add_up(portfolio_db):
    s = compute_summary(1)
    positions = db.get_positions(1)
    assert s["positions"] == len(positions)
    assert s["market_value"] == pytest.approx(sum(p["quantity"] * p["last_close"] for p in positions), abs=0.05)
    assert sum(x["weight"] for x in s["sectors"]) == pytest.approx(1.0, abs=1e-3)
    assert s["history"][-1]["value"] == pytest.approx(s["market_value"], abs=0.05)


def test_unknown_account(service):
    assert service.get_summary(10_000)[0] is None


def test_second_read_comes_from_cache(service):
    assert service.get_summary(1)[1] == "db"
    assert service.get_summary(1)[1] == "l1"
    assert service.get_summary(1, use_cache=False)[1] == "no-cache"


def test_trade_invalidates_so_next_read_is_fresh(service):
    before = service.get_summary(1)[0]
    h = first_holding(1)
    service.trade(1, h["ticker"], "BUY", 100)

    after, source, _ = service.get_summary(1)
    assert source == "db"
    assert after == compute_summary(1)  # cache result == fresh database result
    assert after["market_value"] == pytest.approx(before["market_value"] + 100 * h["last_close"], abs=0.05)


def test_trade_only_invalidates_that_account(service):
    service.get_summary(1)
    service.get_summary(2)
    service.trade(1, first_holding(1)["ticker"], "BUY", 10)
    assert service.get_summary(2)[1] == "l1"


def test_buy_updates_average_cost(service):
    h = first_holding(1)
    service.trade(1, h["ticker"], "BUY", h["quantity"], price=h["cost_basis"] * 3)
    updated = next(p for p in db.get_positions(1) if p["ticker"] == h["ticker"])
    assert updated["quantity"] == 2 * h["quantity"]
    assert updated["cost_basis"] == pytest.approx(h["cost_basis"] * 2)


def test_selling_everything_removes_the_holding(service):
    h = first_holding(1)
    service.trade(1, h["ticker"], "SELL", h["quantity"])
    assert h["ticker"] not in [p["ticker"] for p in db.get_positions(1)]


def test_cannot_sell_more_than_held(service):
    h = first_holding(1)
    with pytest.raises(db.InvalidRequest):
        service.trade(1, h["ticker"], "SELL", h["quantity"] + 1)
    assert db.recent_trades(1) == []  # transaction rolled back


def test_trade_errors(service):
    with pytest.raises(AccountNotFound):
        service.trade(10_000, "AAA", "BUY", 1)
    with pytest.raises(db.InvalidRequest):
        service.trade(1, "NOPE", "BUY", 1)


def test_price_update_invalidates_every_holder(service):
    ticker = first_holding(1)["ticker"]
    holders = set(db.accounts_holding(db.get_security(ticker)["security_id"]))
    all_ids = [a["account_id"] for a in db.list_accounts()]
    for a in all_ids:
        service.get_summary(a)

    result = service.update_price(ticker, 123.45)
    assert result["accounts_invalidated"] == len(holders)

    for a in all_ids:
        summary, source, _ = service.get_summary(a)
        assert source == ("db" if a in holders else "l1")
        assert summary == compute_summary(a), f"account {a} has stale data"


def test_performance_maths():
    history = [("d1", 100.0), ("d2", 110.0), ("d3", 99.0), ("d4", 121.0)]
    p = performance(history)
    assert p["return_1y"] == pytest.approx(0.21)
    assert p["max_drawdown"] == pytest.approx(-0.1)
    assert performance([("d1", 1.0)])["volatility"] is None
