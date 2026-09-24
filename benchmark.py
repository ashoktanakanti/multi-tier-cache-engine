"""
Benchmarks three ways of serving the same "expensive" query
(movie + cast, a join across 3 tables) under repeated access:

  A. Raw SQL every time            (no caching at all)
  B. Redis only                    (cache-aside, single tier)
  C. Local LRU + Redis (tiered)    (the full CacheService)

We simulate realistic traffic: a small "hot set" of movie_ids gets
requested far more often than the rest (Zipf-ish access pattern),
which is exactly the situation caching is built for.
"""
import random
import statistics
import time

import db
from cache_service import CacheService, _cast_key
from redis_cache import RedisCache

N_REQUESTS = 500
HOT_SET_SIZE = 5
HOT_SET_PROBABILITY = 0.8  # 80% of requests hit the hot set


def build_access_pattern(all_ids: list[int]) -> list[int]:
    hot = random.sample(all_ids, k=min(HOT_SET_SIZE, len(all_ids)))
    pattern = []
    for _ in range(N_REQUESTS):
        if random.random() < HOT_SET_PROBABILITY:
            pattern.append(random.choice(hot))
        else:
            pattern.append(random.choice(all_ids))
    return pattern


def time_calls(fn, access_pattern) -> list[float]:
    timings = []
    for movie_id in access_pattern:
        start = time.perf_counter()
        fn(movie_id)
        timings.append((time.perf_counter() - start) * 1000)  # ms
    return timings


def summarize(label: str, timings: list[float]) -> None:
    print(f"{label:<28} avg={statistics.mean(timings):7.3f}ms   "
          f"p95={sorted(timings)[int(len(timings) * 0.95)]:7.3f}ms   "
          f"total={sum(timings):8.2f}ms")


def main():
    all_ids = db.all_movie_ids()
    access_pattern = build_access_pattern(all_ids)

    print(f"Simulating {N_REQUESTS} requests over {len(all_ids)} movies "
          f"({HOT_SET_SIZE}-movie hot set, {int(HOT_SET_PROBABILITY*100)}% of traffic)\n")

    # A. Raw SQL every time
    timings_sql = time_calls(db.get_movie_with_cast, access_pattern)
    summarize("A. Raw SQL (no cache)", timings_sql)

    # B. Redis only
    redis_cache = RedisCache(ttl=300)
    for mid in all_ids:
        redis_cache.invalidate(_cast_key(mid))  # clean slate

    def redis_only_lookup(movie_id):
        key = _cast_key(movie_id)
        value = redis_cache.get(key)
        if value is None:
            value = db.get_movie_with_cast(movie_id)
            redis_cache.put(key, value)
        return value

    timings_redis = time_calls(redis_only_lookup, access_pattern)
    summarize("B. Redis only", timings_redis)

    # C. Tiered: local LRU (DSA) + Redis
    service = CacheService(local_capacity=HOT_SET_SIZE, redis_ttl=300)
    for mid in all_ids:
        service.redis.invalidate(_cast_key(mid))

    timings_tiered = time_calls(service.get_movie_with_cast, access_pattern)
    summarize("C. Local LRU + Redis (tiered)", timings_tiered)

    print(f"\nTier C cache stats: {service.stats}")
    speedup_vs_sql = statistics.mean(timings_sql) / statistics.mean(timings_tiered)
    speedup_vs_redis = statistics.mean(timings_redis) / statistics.mean(timings_tiered)
    print(f"Tiered cache is ~{speedup_vs_sql:.1f}x faster than raw SQL, "
          f"~{speedup_vs_redis:.1f}x faster than Redis-only on this workload.")


if __name__ == "__main__":
    main()
