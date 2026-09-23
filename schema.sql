-- Normalized movie-catalog schema
-- 3 tables, one many-to-many relationship (movies <-> actors), indexes for query speed.

DROP TABLE IF EXISTS movie_actors;
DROP TABLE IF EXISTS movies;
DROP TABLE IF EXISTS actors;

CREATE TABLE movies (
    movie_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    release_year INTEGER NOT NULL,
    genre        TEXT NOT NULL,
    rating       REAL NOT NULL CHECK (rating >= 0 AND rating <= 10)
);

CREATE TABLE actors (
    actor_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    birth_year INTEGER
);

-- Many-to-many join table: a movie has many actors, an actor is in many movies
CREATE TABLE movie_actors (
    movie_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    PRIMARY KEY (movie_id, actor_id),
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES actors(actor_id) ON DELETE CASCADE
);

-- Indexes: speed up the exact lookups/filters our app performs most often
CREATE INDEX idx_movies_genre ON movies(genre);
CREATE INDEX idx_movies_year ON movies(release_year);
CREATE INDEX idx_movie_actors_actor ON movie_actors(actor_id);
