"""
RedisTier — the shared L2 cache.

Why L2 if L1 is faster? L1 lives inside one server process. With several
server processes, each has its own L1 that starts empty. Redis is shared, so
one process's database read warms the cache for all of them, and it survives
app restarts.

Values are stored as JSON with a TTL, so entries expire on their own.

Fail-open: if Redis is down, errors are treated as cache misses and the
request falls through to the database. The cache should make the app
faster, never take it down.
"""
import json

import redis


class RedisTier:
    def __init__(self, client, ttl: int = 300):
        self.client = client
        self.ttl = ttl

    @classmethod
    def from_url(cls, url: str, ttl: int = 300):
        if url == "memory://":
            # Dev only: an in-memory fake Redis for machines without a Redis
            # server. Works the same, but has no network delay, so don't use
            # it for latency measurements.
            import fakeredis

            return cls(fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True), ttl)
        # Short timeouts: a hung Redis must not be slower than just asking the
        # database (~35 ms), or the cache would make things worse, not better.
        client = redis.Redis.from_url(url, decode_responses=True,
                                      socket_timeout=0.05, socket_connect_timeout=0.05)
        return cls(client, ttl)

    def get(self, key):
        try:
            raw = self.client.get(key)
        except redis.RedisError:
            return None
        return None if raw is None else json.loads(raw)

    def put(self, key, value):
        try:
            self.client.set(key, json.dumps(value), ex=self.ttl)
        except redis.RedisError:
            pass

    def delete(self, key):
        try:
            self.client.delete(key)
        except redis.RedisError:
            pass

    def ping(self) -> bool:
        try:
            return bool(self.client.ping())
        except redis.RedisError:
            return False

    def size(self):
        try:
            return self.client.dbsize()
        except redis.RedisError:
            return None
