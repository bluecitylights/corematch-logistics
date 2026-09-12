import pytest
import duckdb
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.database import init_schema
from features.drivers.schemas import DriverCreate, DriverUpdate
from features.drivers import service
from features.drivers.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_driver_schema():
    with pytest.raises(ValidationError):
        DriverCreate(driver_id="D1", location_id="not_an_int")
    
    drv = DriverCreate(driver_id="D1", location_id=1, skill_adr=True)
    assert drv.skill_adr is True
    assert drv.is_active is True

def test_service_crud(tmp_path):
    con = setup_db(tmp_path)
    
    # Needs a location first because of sequence/fk behavior in duckdb model setup
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    # Create
    drv1 = service.create_driver(con, DriverCreate(driver_id="D1", location_id=1, skill_adr=True))
    assert drv1.driver_id == "D1"
    assert drv1.skill_adr is True
    
    # List
    assert len(service.list_drivers(con)) == 1
    
    # Update
    drv2 = service.update_driver(con, "D1", DriverUpdate(skill_ehbo=True))
    assert drv2.skill_ehbo is True
    assert drv2.skill_adr is True # Persisted
    
    # Delete (soft)
    drv3 = service.delete_driver(con, "D1")
    assert drv3.is_active is False
    
    # List excludes inactive by default
    assert len(service.list_drivers(con)) == 0
    assert len(service.list_drivers(con, include_inactive=True)) == 1

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    from features.drivers.router import get_db_con
    app.dependency_overrides[get_db_con] = lambda: con
    
    # POST
    resp = client.post("/api/drivers", json={"driver_id": "D2", "location_id": 1, "skill_adr": True})
    assert resp.status_code == 200
    assert resp.json()["driver_id"] == "D2"
    
    # PATCH
    resp = client.patch("/api/drivers/D2", json={"skill_ehbo": True})
    assert resp.status_code == 200
    assert resp.json()["skill_ehbo"] is True
    
    # DELETE
    resp = client.delete("/api/drivers/D2")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

