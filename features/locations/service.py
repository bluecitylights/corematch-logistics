import math
import duckdb
from typing import Sequence
from core.database import query_models, execute_update, query_model_or_none, api_rows
from features.locations.schemas import Location, LocationCreate, DistanceMatrixItem

def _distance(origin: tuple[str, str, float, float], destination: tuple[str, str, float, float]) -> tuple[int, int]:
    lat1, lon1 = math.radians(origin[2]), math.radians(origin[3])
    lat2, lon2 = math.radians(destination[2]), math.radians(destination[3])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    km = 6371 * 2 * math.asin(math.sqrt(a))
    return round(km * 1000), 0 if origin[0] == destination[0] else round((km / 50) * 60)

def rebuild_distance_matrix(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        "SELECT zip, city, latitude, longitude FROM locations ORDER BY zip"
    ).fetchall()
    matrix = [
        (origin[0], destination[0], *_distance(origin, destination))
        for origin in rows
        for destination in rows
    ]
    con.execute("DELETE FROM distance_matrix")
    con.executemany(
        """
        INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min)
        VALUES (?, ?, ?, ?)
        """,
        matrix,
    )

def list_locations(con: duckdb.DuckDBPyConnection) -> Sequence[Location]:
    return query_models(Location, con, "SELECT * FROM locations ORDER BY zip")

def create_location(con: duckdb.DuckDBPyConnection, payload: LocationCreate) -> Location:
    con.execute(
        "INSERT INTO locations (zip, city, latitude, longitude) VALUES (?, ?, ?, ?) ON CONFLICT (zip) DO UPDATE SET city=EXCLUDED.city, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude",
        [payload.zip, payload.city, payload.latitude, payload.longitude],
    )
    rebuild_distance_matrix(con)
    loc = query_model_or_none(Location, con, "SELECT * FROM locations WHERE zip = ?", [payload.zip])
    if loc is None:
        raise ValueError("Failed to retrieve created location")
    return loc

def get_distance_matrix(con: duckdb.DuckDBPyConnection, origin_zip: str) -> Sequence[DistanceMatrixItem]:
    return query_models(
        DistanceMatrixItem,
        con,
        "SELECT origin_zip, dest_zip, distance_m, travel_time_min FROM distance_matrix WHERE origin_zip = ?",
        [origin_zip],
    )

