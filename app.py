"""
FastAPI wrapper around CacheService — turns the project into a real,
hittable service instead of just scripts.

Endpoints:
  GET  /movies/{movie_id}              -> movie + cast (through the cache tiers)
  GET  /movies/genre/{genre}/top       -> top-rated movies in a genre (uncached, direct SQL)
  PUT  /movies/{movie_id}/rating       -> update rating; invalidates both cache tiers
  GET  /cache/stats                    -> L1/L2/DB hit counters
  GET  /health                         -> liveness + Redis connectivity check

Run with:  uvicorn app:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException, Query

import db
from cache_service import CacheService

app = FastAPI(title="Movie Catalog Cache Demo")
service = CacheService(local_capacity=10, redis_ttl=60, policy="lru")


@app.get("/health")
def health():
    return {"status": "ok", "redis_connected": service.redis.ping()}


@app.get("/movies/{movie_id}")
def get_movie(movie_id: int):
    movie = service.get_movie_with_cast(movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


@app.get("/movies/genre/{genre}/top")
def top_movies_by_genre(genre: str, limit: int = Query(5, ge=1, le=50)):
    # Deliberately not cached here — shows the contrast with the cached endpoint above.
    return db.get_top_rated_by_genre(genre, limit)


@app.put("/movies/{movie_id}/rating")
def update_rating(movie_id: int, rating: float = Query(..., ge=0, le=10)):
    existing = db.get_movie_by_id(movie_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    service.update_rating(movie_id, rating)
    return {"movie_id": movie_id, "new_rating": rating, "cache_invalidated": True}


@app.get("/cache/stats")
def cache_stats():
    return {"policy": service.policy, **service.stats}
