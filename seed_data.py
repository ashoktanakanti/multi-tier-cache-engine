"""Creates movies.db from schema.sql and fills it with sample data."""
import sqlite3
import random

DB_PATH = "movies.db"

GENRES = ["Action", "Drama", "Comedy", "Sci-Fi", "Thriller", "Animation"]

TITLES = [
    "Neon Horizon", "The Quiet Storm", "Last Light", "Iron Orbit",
    "Whispering Pines", "Chrome Hearts", "The Long Descent", "Paper Moonlight",
    "Static Bloom", "Glass Tiger", "Midnight Ferry", "Hollow Crown",
    "The Silver Static", "Echo Chamber", "Rust Belt", "Velvet Signal",
    "The Last Cartographer", "Salt and Circuit", "Faded Frequencies",
    "The Amber Room",
]

ACTOR_NAMES = [
    "Maya Chen", "Ravi Kapoor", "Liam O'Connor", "Sofia Reyes", "Ken Watanabe Jr.",
    "Priya Nair", "Oscar Lindqvist", "Amara Okafor", "Diego Fernandez", "Elin Karlsson",
    "Noor Hassan", "Tom Bellweather", "Yuki Tanaka", "Grace Abimbola", "Marco Rossi",
]


def build_database():
    conn = sqlite3.connect(DB_PATH)
    with open("schema.sql") as f:
        conn.executescript(f.read())

    cur = conn.cursor()

    movie_ids = []
    for title in TITLES:
        cur.execute(
            "INSERT INTO movies (title, release_year, genre, rating) VALUES (?, ?, ?, ?)",
            (title, random.randint(1998, 2026), random.choice(GENRES), round(random.uniform(4.0, 9.5), 1)),
        )
        movie_ids.append(cur.lastrowid)

    actor_ids = []
    for name in ACTOR_NAMES:
        cur.execute(
            "INSERT INTO actors (name, birth_year) VALUES (?, ?)",
            (name, random.randint(1965, 2001)),
        )
        actor_ids.append(cur.lastrowid)

    # Cast each movie with 2-5 random actors
    for mid in movie_ids:
        cast = random.sample(actor_ids, k=random.randint(2, 5))
        for aid in cast:
            cur.execute(
                "INSERT OR IGNORE INTO movie_actors (movie_id, actor_id) VALUES (?, ?)",
                (mid, aid),
            )

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH}: {len(movie_ids)} movies, {len(actor_ids)} actors.")


if __name__ == "__main__":
    build_database()
