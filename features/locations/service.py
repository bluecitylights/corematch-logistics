import math
import duckdb
from typing import Generator, Sequence, Any
from core.base_service import BaseService
from core.database import get_db, query_models, query_model_or_none
from features.locations.schemas import Location, LocationCreate, DistanceMatrixItem

def _distance(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float, is_same: bool) -> tuple[int, int]:
    lat1, lon1 = math.radians(lat1_deg), math.radians(lon1_deg)
    lat2, lon2 = math.radians(lat2_deg), math.radians(lon2_deg)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    km = 6371 * 2 * math.asin(math.sqrt(a))
    return round(km * 1000), 0 if is_same else round((km / 50) * 60)


class LocationService(BaseService):
    """Domain service for managing warehouse and delivery locations."""

    def rebuild_distance_matrix(self) -> None:
        rows = self.fetch_all("SELECT location_index, latitude, longitude FROM locations ORDER BY location_index")
        matrix = [
            (
                orig_idx, 
                dest_idx, 
                *_distance(orig_lat, orig_lon, dest_lat, dest_lon, orig_idx == dest_idx)
            )
            for orig_idx, orig_lat, orig_lon in rows
            for dest_idx, dest_lat, dest_lon in rows
        ]
        self.execute("DELETE FROM distance_matrix")
        self.executemany(
            """
            INSERT INTO distance_matrix (origin_location_index, dest_location_index, distance_m, travel_time_min)
            VALUES (?, ?, ?, ?)
            """,
            matrix,
        )

    def list_locations(self) -> Sequence[Location]:
        return self.query_models(Location, "SELECT * FROM locations ORDER BY location_index")

    def get_location_by_zip(self, zip_code: str) -> Location | None:
        return self.query_model_or_none(
            Location,
            "SELECT * FROM locations WHERE zip = ?",
            [zip_code],
        )
    
    

    def create_location(self, payload: LocationCreate) -> Location:
        self.execute(
            "INSERT INTO locations (zip, city, latitude, longitude) VALUES (?, ?, ?, ?) ON CONFLICT (zip) DO UPDATE SET city=EXCLUDED.city, latitude=EXCLUDED.latitude, longitude=EXCLUDED.longitude",
            [payload.zip, payload.city, payload.latitude, payload.longitude],
        )
        self.rebuild_distance_matrix()
        loc = self.query_model_or_none(Location, "SELECT * FROM locations WHERE zip = ?", [payload.zip])
        if loc is None:
            raise ValueError("Failed to retrieve created location")
        return loc

    def get_distance_matrix(self, origin_location_index: int) -> Sequence[DistanceMatrixItem]:
        return self.query_models(
            DistanceMatrixItem,
            "SELECT origin_location_index, dest_location_index, distance_m, travel_time_min FROM distance_matrix WHERE origin_location_index = ?",
            [origin_location_index],
        )

    def get_distance_matrix_by_zip(self, origin_location_zip: str) -> Sequence[DistanceMatrixItem]:
        loc = self.get_location_by_zip(origin_location_zip)
        if not loc:
            raise ValueError(f"Location not found for zip: {origin_location_zip}")
        return self.get_distance_matrix(loc.location_id)

def get_location_service() -> Generator[LocationService, None, None]:
    with get_db() as con:
        yield LocationService(con)


location_service = LocationService()

rebuild_distance_matrix = location_service.rebuild_distance_matrix
list_locations = location_service.list_locations
create_location = location_service.create_location
get_distance_matrix = location_service.get_distance_matrix