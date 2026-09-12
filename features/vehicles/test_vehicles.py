import pytest
import duckdb
from fastapi.testclient import TestClient

from core.database import init_schema
from features.vehicles.schemas import VehicleCreate, VehicleUpdate
from features.vehicles.service import VehicleService, get_vehicle_service
from features.vehicles.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_service_crud(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    veh_service = VehicleService(con)
    
    # Create
    veh1 = veh_service.create_vehicle(VehicleCreate(
        vehicle_id="V1",
        license_plate="AB-12",
        location_id=1,
        spec_liftgate=True
    ))
    assert veh1.vehicle_id == "V1"
    assert veh1.spec_liftgate is True
    assert veh1.spec_refrigerated is False
    
    # List
    assert len(veh_service.list_vehicles()) == 1
    
    # Update
    veh2 = veh_service.update_vehicle("V1", VehicleUpdate(spec_refrigerated=True))
    assert veh2.spec_refrigerated is True
    assert veh2.spec_liftgate is True
    
    # Delete (soft)
    veh3 = veh_service.delete_vehicle("V1")
    assert veh3.is_active is False

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    app.dependency_overrides[get_vehicle_service] = lambda: VehicleService(con)
    
    resp = client.post("/api/vehicles", json={"vehicle_id": "V2", "license_plate": "XY-99", "location_id": 1, "spec_liftgate": True})
    assert resp.status_code == 200
    assert resp.json()["vehicle_id"] == "V2"
    
    resp = client.patch("/api/vehicles/V2", json={"spec_refrigerated": True})
    assert resp.status_code == 200
    assert resp.json()["spec_refrigerated"] is True
    
    resp = client.delete("/api/vehicles/V2")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
