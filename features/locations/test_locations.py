import pytest
import duckdb
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.database import init_schema
from features.locations.schemas import LocationCreate, Location, DistanceMatrixItem
from features.locations import service
from features.locations.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_location_schema():
    with pytest.raises(ValidationError):
        LocationCreate(zip="1234", city="City", latitude="not_a_float", longitude=1.0)
    
    loc = LocationCreate(zip="1234", city="City", latitude=52.0, longitude=4.0)
    assert loc.zip == "1234"

def test_service_crud_and_matrix(tmp_path):
    con = setup_db(tmp_path)
    
    # Create locations
    loc1 = service.create_location(con, LocationCreate(zip="1000", city="City A", latitude=10.0, longitude=20.0))
    loc2 = service.create_location(con, LocationCreate(zip="2000", city="City B", latitude=11.0, longitude=21.0))
    
    assert loc1.location_id >= 0
    assert loc1.zip == "1000"
    
    # List locations
    locs = service.list_locations(con)
    assert len(locs) == 2
    
    # Distance matrix
    matrix = service.get_distance_matrix(con, "1000")
    assert len(matrix) == 2  # 1000->1000, 1000->2000
    assert any(m.dest_zip == "2000" for m in matrix)

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path, monkeypatch):
    con = setup_db(tmp_path)
    
    # We monkeypatch the dependency
    def override_get_db_con():
        yield con
    app.dependency_overrides[router.routes[0].endpoint] = override_get_db_con # Actually lets just patch get_db_con globally
    
    # Simple dependency override
    from features.locations.router import get_db_con
    app.dependency_overrides[get_db_con] = lambda: con
    
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

