from datetime import date

import fakeredis
import pytest

from cache_engine import RedisTier
from portfolio import db, seed


@pytest.fixture(scope="session")
def _template_db(tmp_path_factory):
    """A small seeded database, built once per test run."""
    path = tmp_path_factory.mktemp("db") / "template.db"
    seed.build(str(path), n_securities=40, n_accounts=12, n_days=40, positions=(4, 10),
               seed=7, end=date(2026, 6, 30))
    return path


@pytest.fixture
def portfolio_db(_template_db, tmp_path, monkeypatch):
    """A fresh copy of the small database for each test."""
    path = tmp_path / "portfolio.db"
    path.write_bytes(_template_db.read_bytes())
    monkeypatch.setattr(db, "DB_PATH", str(path))
    return path


@pytest.fixture
def fake_redis():
    return RedisTier(fakeredis.FakeRedis(decode_responses=True))
