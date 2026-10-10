import pytest
from fastapi.testclient import TestClient

from portfolio import api, db


@pytest.fixture
def client(portfolio_db, monkeypatch):
    monkeypatch.setenv("REDIS_URL", "memory://")
    with TestClient(api.app) as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "policy": "lru", "redis": "in-memory fake"}


def test_list_accounts(client):
    page = client.get("/accounts", params={"limit": 5, "offset": 5}).json()
    assert [a["account_id"] for a in page] == [6, 7, 8, 9, 10]
    assert client.get("/accounts", params={"limit": 0}).status_code == 422


def test_summary_x_cache_header(client):
    first = client.get("/accounts/1/summary")
    second = client.get("/accounts/1/summary")
    no_cache = client.get("/accounts/1/summary", params={"use_cache": False})
    assert [r.headers["X-Cache"] for r in (first, second, no_cache)] == ["DB", "L1", "NO-CACHE"]
    assert first.json() == second.json() == no_cache.json()


def test_unknown_account_404(client):
    assert client.get("/accounts/99999/summary").status_code == 404
    assert client.get("/cache/lookup/99999").status_code == 404


def test_trade_then_read_misses(client):
    ticker = db.get_positions(1)[0]["ticker"]
    client.get("/accounts/1/summary")
    r = client.post("/accounts/1/trades", json={"ticker": ticker, "side": "BUY", "quantity": 10})
    assert r.status_code == 201
    assert client.get("/accounts/1/summary").headers["X-Cache"] == "DB"
    assert client.get("/accounts/1/trades").json()[0]["ticker"] == ticker


@pytest.mark.parametrize("body", [
    {"ticker": "AAA", "side": "HOLD", "quantity": 1},
    {"ticker": "AAA", "side": "BUY", "quantity": -5},
    {"ticker": "NOPE", "side": "BUY", "quantity": 1},
])
def test_bad_trades_rejected(client, body):
    assert client.post("/accounts/1/trades", json=body).status_code == 422


def test_price_update(client):
    ticker = db.get_positions(1)[0]["ticker"]
    client.get("/accounts/1/summary")
    r = client.put(f"/securities/{ticker}/price", json={"close": 50})
    assert r.status_code == 200 and r.json()["accounts_invalidated"] >= 1
    assert client.get("/accounts/1/summary").headers["X-Cache"] == "DB"
    assert client.put("/securities/NOPE/price", json={"close": 1}).status_code == 404


def test_lookup_trace(client):
    cold = client.get("/cache/lookup/1").json()
    assert cold["source"] == "db"
    assert [s["tier"] for s in cold["steps"]] == ["l1", "l2", "db", "l2", "l1"]
    warm = client.get("/cache/lookup/1").json()
    assert warm["source"] == "l1" and len(warm["steps"]) == 1


def test_stats_events_and_clear(client):
    client.get("/accounts/1/summary")
    client.get("/accounts/1/summary")
    stats = client.get("/cache/stats").json()
    assert stats["hits"]["db"] == 1 and stats["hits"]["l1"] == 1
    assert stats["l1"]["size"] == 1 and stats["l2"]["keys"] == 1

    events = client.get("/cache/events").json()
    assert [e["kind"] for e in events] == ["load", "hit"]

    assert client.delete("/cache").status_code == 204
    assert client.get("/cache/stats").json()["requests"] == 0
    # L1 was cleared but Redis still has the value
    assert client.get("/accounts/1/summary").headers["X-Cache"] == "L2"


def test_security_search(client):
    ticker = db.get_positions(1)[0]["ticker"]
    assert client.get("/securities", params={"q": ticker}).json()[0]["ticker"] == ticker
