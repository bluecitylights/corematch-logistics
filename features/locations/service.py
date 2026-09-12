import math
import duckdb
from typing import Any, Sequence
from core.base_service import BaseService
from core.database import query_models, query_model_or_none
from features.locations.schemas import Location, LocationCreate, DistanceMatrixItem

def _distance(origin: tuple[str, str, float, float], destination: tuple[str, str, float, float]) -> tuple[int, int]:
    lat1, lon1 = math.radians(origin[2]), math.radians(origin[3])
    lat2, lon2 = math.radians(destination[2]), math.radians(destination[3])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    km = 6371 * 2 * math.asin(math.sqrt(a))
    return round(km * 1000), 0 if origin[0] == destination[0] else round((km / 50) * 60)


class LocationService(BaseService):
    """Domain service for managing warehouse and delivery locations."""

    def rebuild_distance_matrix(self, con: duckdb.DuckDBPyConnection | None = None) -> None:
        with self._get_con(con) as c:
            rows = c.execute(
                "SELECT zip, city, latitude, longitude FROM locations ORDER BY zip"
            ).fetchall()
            matrix = [
                (origin[0], destination[0], *_distance(origin, destination))
                for origin in rows
                for destination in rows
            ]
            c.execute("DELETE FROM distance_matrix")
            c.executemany(
                """
                INSERT INTO distance_matrix (origin_zip, dest_zip, distance_m, travel_time_min)
                VALUES (?, ?, ?, ?)
                """,
                matrix,
            )

    def list_locations(self, con: duckdb.DuckDBPyConnection | None = None) -> Sequence[Location]:
        with self._get_con(con) as c:
            return query_models(Location, c, "SELECT * FROM locations ORDER BY zip")

    def create_location(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Location:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            payload = arg2
        else:
            payload = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            c.execute(
                "INSERT INTO locations (zip, city, latitude, longitude) VALUES (?, ?, ?, ?) ON CONFLICT (zip) DO UPDATE SET city=EXCLUDED.city, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude",
                [payload.zip, payload.city, payload.latitude, payload.longitude],
            )
            self.rebuild_distance_matrix(c)
            loc = query_model_or_none(Location, c, "SELECT * FROM locations WHERE zip = ?", [payload.zip])
            if loc is None:
                raise ValueError("Failed to retrieve created location")
            return loc

    def get_distance_matrix(self, arg1: Any, arg2: Any = None, con: duckdb.DuckDBPyConnection | None = None) -> Sequence[DistanceMatrixItem]:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c_passed = arg1
            origin_zip = arg2
        else:
            origin_zip = arg1
            c_passed = con or (arg2 if isinstance(arg2, duckdb.DuckDBPyConnection) else None)
        with self._get_con(c_passed) as c:
            return query_models(
                DistanceMatrixItem,
                c,
                "SELECT origin_zip, dest_zip, distance_m, travel_time_min FROM distance_matrix WHERE origin_zip = ?",
                [origin_zip],
            )


location_service = LocationService()

# Backward-compatibility aliases
rebuild_distance_matrix = location_service.rebuild_distance_matrix
list_locations = location_service.list_locations
create_location = location_service.create_location
get_distance_matrix = location_service.get_distance_matrix

