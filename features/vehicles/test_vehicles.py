import pytest
import duckdb
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.database import init_schema
from features.vehicles.schemas import VehicleCreate, VehicleUpdate
from features.vehicles import service
from features.vehicles.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_vehicle_schema():
    with pytest.raises(ValidationError):
        VehicleCreate(vehicle_id="V1", license_plate="AA", location_id="invalid")
    
    veh = VehicleCreate(vehicle_id="V1", license_plate="AA", location_id=1, spec_liftgate=True)
    assert veh.spec_liftgate is True
    assert veh.is_active is True

def test_service_crud(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    veh1 = service.create_vehicle(con, VehicleCreate(vehicle_id="V1", license_plate="AB-12", location_id=1, spec_liftgate=True))
    assert veh1.vehicle_id == "V1"
    assert veh1.spec_liftgate is True
    
    assert len(service.list_vehicles(con)) == 1
    
    veh2 = service.update_vehicle(con, "V1", VehicleUpdate(spec_refrigerated=True))
    assert veh2.spec_refrigerated is True
    
    veh3 = service.delete_vehicle(con, "V1")
    assert veh3.is_active is False
    
    assert len(service.list_vehicles(con)) == 0
    assert len(service.list_vehicles(con, include_inactive=True)) == 1

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    from features.vehicles.router import get_db_con
    app.dependency_overrides[get_db_con] = lambda: con
    
    resp = client.post("/api/vehicles", json={"vehicle_id": "V2", "license_plate": "XY-99", "location_id": 1, "spec_liftgate": True})
    assert resp.status_code == 200
    assert resp.json()["vehicle_id"] == "V2"
    
    resp = client.patch("/api/vehicles/V2", json={"spec_refrigerated": True})
    assert resp.status_code == 200
    assert resp.json()["spec_refrigerated"] is True
    
    resp = client.delete("/api/vehicles/V2")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

