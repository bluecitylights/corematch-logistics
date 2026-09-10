"""Location reference data and distance-matrix initialization."""

import math

import duckdb


LOCATIONS = (
    ("1544", "Zaandijk", 52.4833, 4.8167),
    ("1012", "Amsterdam", 52.3728, 4.8936),
    ("2011", "Haarlem", 52.3888, 4.6388),
    ("1811", "Alkmaar", 52.6323, 4.7456),
    ("1506", "Zaandam", 52.4388, 4.8264),
    ("1118", "Schiphol", 52.3105, 4.7683),
    ("3511", "Utrecht", 52.0907, 5.1214),
    ("3011", "Rotterdam", 51.9244, 4.4777),
    ("2511", "Den Haag", 52.0799, 4.3113),
    ("2801", "Gouda", 52.0116, 4.7104),
)


def _distance(origin: tuple[str, str, float, float], destination: tuple[str, str, float, float]) -> tuple[int, int]:
    lat1, lon1 = math.radians(origin[2]), math.radians(origin[3])
    lat2, lon2 = math.radians(destination[2]), math.radians(destination[3])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    km = 6371 * 2 * math.asin(math.sqrt(a))
    return round(km * 1000), 0 if origin[0] == destination[0] else round((km / 50) * 60)


def ensure_location_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create and seed location reference tables without replacing existing data."""
    con.execute("CREATE SEQUENCE IF NOT EXISTS location_seq START 0 MINVALUE 0")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS locations (
            location_id INTEGER DEFAULT nextval('location_seq') UNIQUE,
            zip VARCHAR PRIMARY KEY,
            city VARCHAR NOT NULL,
            latitude DOUBLE NOT NULL,
            longitude DOUBLE NOT NULL
        )
        """
    )
    columns = {
        row[0]
        for row in con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'locations'"
        ).fetchall()
    }
    if "location_id" not in columns:
        con.execute(
            "ALTER TABLE locations ADD COLUMN location_id INTEGER DEFAULT nextval('location_seq')"
        )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS distance_matrix (
            origin_zip VARCHAR NOT NULL,
            dest_zip VARCHAR NOT NULL,
            distance_m INTEGER NOT NULL,
            travel_time_min INTEGER NOT NULL,
            PRIMARY KEY (origin_zip, dest_zip)
        )
        """
    )
    con.executemany(
        "INSERT INTO locations (zip, city, latitude, longitude) VALUES (?, ?, ?, ?) ON CONFLICT (zip) DO NOTHING",
        LOCATIONS,
    )
    for table, old_column, new_column in (
        ("drivers", "location", "location_id"),
        ("vehicles", "location", "location_id"),
        ("orders", "destination", "destination_location_id"),
    ):
        columns = {
            row[0]
            for row in con.execute(
                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'"
            ).fetchall()
        }
        if new_column not in columns:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {new_column} INTEGER")
        if old_column in columns:
            con.execute(
                f"""
                UPDATE {table}
                SET {new_column} = (
                    SELECT location_id FROM locations
                    WHERE zip = CAST({old_column} AS VARCHAR) OR city = {old_column}
                )
                WHERE {new_column} IS NULL
                """
            )
            con.execute(f"ALTER TABLE {table} DROP COLUMN {old_column}")

    rows = con.execute(
        "SELECT zip, city, latitude, longitude FROM locations ORDER BY zip"
    ).fetchall()
    matrix = [
        (origin[0], destination[0], *_distance(origin, destination))
        for origin in rows
        for destination in rows
    ]
    con.executemany(
        """
        INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (origin_zip, dest_zip) DO NOTHING
        """,
        matrix,
    )
