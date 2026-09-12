import pytest
import duckdb
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.database import init_schema
from features.drivers.schemas import DriverCreate, DriverUpdate
from features.drivers.service import DriverService, get_driver_service
from features.drivers.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_driver_schema():
    with pytest.raises(ValidationError):
        DriverCreate(name="D1", location_id="not_an_int")
    
    drv = DriverCreate(name="D1", location_id=0, skill_adr=True)
    assert drv.skill_adr is True
    assert drv.is_active is True

def test_service_crud(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (zip, city, latitude, longitude) VALUES ('1000', 'A', 1, 1)")
    
    drv_service = DriverService(con)
    
    # Create
    drv1 = drv_service.create_driver(DriverCreate(name="D1", location_id=0, skill_adr=True))
    assert drv1.name == "D1"
    assert drv1.skill_adr is True
    
    # List
    assert len(drv_service.list_drivers()) == 1
    
    # Update
    drv2 = drv_service.update_driver(drv1.driver_id, DriverUpdate(skill_ehbo=True))
    assert drv2.skill_ehbo is True
    assert drv2.skill_adr is True # Persisted
    
    # Delete (soft)
    drv3 = drv_service.delete_driver(drv1.driver_id)
    assert drv3.is_active is False

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (zip, city, latitude, longitude) VALUES ('1000', 'A', 1, 1)")
    app.dependency_overrides[get_driver_service] = lambda: DriverService(con)
    
    # POST
    resp = client.post("/api/drivers", json={"name": "D2", "location_id": 0, "skill_adr": True})
    assert resp.status_code == 200
    assert resp.json()["name"] == "D2"
    
    # PATCH
    resp = client.patch("/api/drivers/0", json={"skill_ehbo": True})
    assert resp.status_code == 200
    assert resp.json()["skill_ehbo"] is True
    
    # DELETE
    resp = client.delete("/api/drivers/0")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
