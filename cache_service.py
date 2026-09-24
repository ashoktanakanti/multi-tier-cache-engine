"""
CacheService — glues everything together with the cache-aside pattern:

    1. Check the in-process LRU cache (your DSA structure)  -> L1, fastest
    2. Miss? Check Redis                                     -> L2, still fast
    3. Miss? Query SQLite (the source of truth)               -> slow, disk I/O
    4. On a DB read, populate both cache tiers on the way back up.
    5. On a write, invalidate the key in both tiers so nobody serves stale data.

This mirrors how real systems layer an in-process cache in front of a
shared cache (Redis) in front of a database, and is the same tiering you'd
sketch in a system-design interview.
"""
import db
from lru_cache import LRUCache
from lfu_cache import LFUCache
from redis_cache import RedisCache


def _cast_key(movie_id: int) -> str:
    return f"movie_cast:{movie_id}"


class CacheService:
    def __init__(self, local_capacity: int = 20, redis_ttl: int = 60, policy: str = "lru"):
        if policy == "lru":
            self.local = LRUCache(capacity=local_capacity)
        elif policy == "lfu":
            self.local = LFUCache(capacity=local_capacity)
        else:
            raise ValueError("policy must be 'lru' or 'lfu'")
        self.policy = policy
        self.redis = RedisCache(ttl=redis_ttl)
        self.stats = {"l1_hits": 0, "l2_hits": 0, "db_hits": 0}

    def get_movie_with_cast(self, movie_id: int) -> dict | None:
        key = _cast_key(movie_id)

        # --- Tier 1: local DSA cache ---
        value = self.local.get(key)
        if value is not None:
            self.stats["l1_hits"] += 1
            return value

        # --- Tier 2: Redis ---
        value = self.redis.get(key)
        if value is not None:
            self.stats["l2_hits"] += 1
            self.local.put(key, value)  # promote into L1
            return value

        # --- Tier 3: source of truth ---
        value = db.get_movie_with_cast(movie_id)
        self.stats["db_hits"] += 1
        if value is not None:
            self.redis.put(key, value)
            self.local.put(key, value)
        return value

    def update_rating(self, movie_id: int, new_rating: float) -> None:
        """Write path: update the DB, then invalidate both cache tiers."""
        db.update_movie_rating(movie_id, new_rating)
        key = _cast_key(movie_id)
        self.local.invalidate(key)
        self.redis.invalidate(key)

    def reset_stats(self) -> None:
        self.stats = {"l1_hits": 0, "l2_hits": 0, "db_hits": 0}
