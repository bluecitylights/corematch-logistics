import pytest
import duckdb
from fastapi.testclient import TestClient

from core.database import init_schema
from features.locations.schemas import LocationCreate
from features.locations.service import LocationService, get_location_service
from features.locations.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_service_crud_and_matrix(tmp_path):
    con = setup_db(tmp_path)
    loc_service = LocationService(con)
    
    # 1. Create initial locations
    loc1 = loc_service.create_location(LocationCreate(zip="1000", city="City A", latitude=50.8503, longitude=4.3517))
    assert loc1.zip == "1000"
    
    loc2 = loc_service.create_location(LocationCreate(zip="2000", city="City B", latitude=51.2194, longitude=4.4025))
    assert loc2.zip == "2000"
    
    # List
    locations = loc_service.list_locations()
    assert len(locations) == 2
    
    # Matrix verification
    matrix = loc_service.get_distance_matrix_by_zip("1000")
    assert len(matrix) == 2
    for item in matrix:
        if item.dest_zip == "1000":
            assert item.distance_m == 0
            assert item.travel_time_min == 0
        elif item.dest_zip == "2000":
            assert item.distance_m > 40000
            assert item.travel_time_min > 0

    # Test update upsert
    loc1_updated = loc_service.create_location(LocationCreate(zip="1000", city="Updated City A", latitude=50.8503, longitude=4.3517))
    assert loc1_updated.city == "Updated City A"
    matrix = loc_service.get_distance_matrix("1000")
    assert any(m.dest_zip == "2000" for m in matrix)

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    app.dependency_overrides[get_location_service] = lambda: LocationService(con)
    
    # POST
    resp = client.post("/api/locations", json={"zip": "3000", "city": "City C", "latitude": 1.0, "longitude": 1.0})
    assert resp.status_code == 200
    assert resp.json()["zip"] == "3000"
    
    # GET
    resp = client.get("/api/locations")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    
    # GET matrix
    resp = client.get("/api/distance-matrix/3000")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
