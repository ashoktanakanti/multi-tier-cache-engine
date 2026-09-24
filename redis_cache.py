"""
Thin wrapper around redis-py — this is the real "cache DB" tier.
Kept deliberately simple: JSON-serialize values, apply a TTL on every write,
so entries expire even if we forget to invalidate them explicitly.
"""
import json
import redis

DEFAULT_TTL_SECONDS = 60


class RedisCache:
    def __init__(self, host="localhost", port=6379, db=0, ttl=DEFAULT_TTL_SECONDS):
        self.client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.ttl = ttl

    def get(self, key: str):
        # Fail open: if Redis is unreachable, treat it as a cache miss rather
        # than crashing the request. A cache DB should never be a single
        # point of failure for the app it's speeding up.
        try:
            raw = self.client.get(key)
        except redis.exceptions.ConnectionError:
            return None
        if raw is None:
            return None
        return json.loads(raw)

    def put(self, key: str, value) -> None:
        try:
            self.client.set(key, json.dumps(value), ex=self.ttl)
        except redis.exceptions.ConnectionError:
            pass  # best-effort cache write; DB remains the source of truth

    def invalidate(self, key: str) -> None:
        try:
            self.client.delete(key)
        except redis.exceptions.ConnectionError:
            pass

    def ping(self) -> bool:
        try:
            return self.client.ping()
        except redis.exceptions.ConnectionError:
            return False
