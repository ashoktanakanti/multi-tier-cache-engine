"""
Data Access Layer (DAO) — the "attic" in the toy-box analogy.
Raw SQL, no ORM, so every query that hits the database is explicit and visible.
This is the single source of truth. The cache tiers never store anything
that didn't come from here first.
"""
import sqlite3
from contextlib import contextmanager

DB_PATH = "movies.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_movie_by_id(movie_id: int) -> dict | None:
    """Simple point lookup — cheap, but still a disk round-trip."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM movies WHERE movie_id = ?", (movie_id,)
        ).fetchone()
        return dict(row) if row else None


def get_movie_with_cast(movie_id: int) -> dict | None:
    """
    The 'expensive' query: a join across movies -> movie_actors -> actors,
    aggregated into one payload. This is the kind of query caching is FOR —
    cheap to serve from cache, costly to recompute on every request.
    """
    with get_conn() as conn:
        movie_row = conn.execute(
            "SELECT * FROM movies WHERE movie_id = ?", (movie_id,)
        ).fetchone()
        if not movie_row:
            return None

        cast_rows = conn.execute(
            """
            SELECT a.actor_id, a.name, a.birth_year
            FROM actors a
            JOIN movie_actors ma ON ma.actor_id = a.actor_id
            WHERE ma.movie_id = ?
            ORDER BY a.name
            """,
            (movie_id,),
        ).fetchall()

        movie = dict(movie_row)
        movie["cast"] = [dict(r) for r in cast_rows]
        return movie


def get_top_rated_by_genre(genre: str, limit: int = 5) -> list[dict]:
    """Filter + sort query — benefits from the idx_movies_genre index."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT movie_id, title, release_year, genre, rating
            FROM movies
            WHERE genre = ?
            ORDER BY rating DESC
            LIMIT ?
            """,
            (genre, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def update_movie_rating(movie_id: int, new_rating: float) -> None:
    """A write path — this is what triggers cache invalidation."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE movies SET rating = ? WHERE movie_id = ?", (new_rating, movie_id)
        )
        conn.commit()


def all_movie_ids() -> list[int]:
    with get_conn() as conn:
        rows = conn.execute("SELECT movie_id FROM movies").fetchall()
        return [r["movie_id"] for r in rows]
