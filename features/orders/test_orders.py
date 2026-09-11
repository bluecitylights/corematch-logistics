import pytest
import duckdb
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.database import init_schema
from features.orders.schemas import OrderCreate, OrderUpdate
from features.orders import service
from features.orders.router import router

def setup_db(tmp_path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(tmp_path / "test.duckdb"))
    init_schema(con)
    return con

def test_order_schema():
    with pytest.raises(ValidationError):
        OrderCreate(order_id="O1", destination_location_id="invalid")
    
    order = OrderCreate(order_id="O1", destination_location_id=1, req_driver_adr=True)
    assert order.req_driver_adr is True
    assert order.req_vehicle_liftgate is False

def test_service_crud(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    order1 = service.create_order(con, OrderCreate(order_id="O1", destination_location_id=1, req_driver_adr=True))
    assert order1.order_id == "O1"
    assert order1.req_driver_adr is True
    
    assert len(service.list_orders(con)) == 1
    
    order2 = service.update_order(con, "O1", OrderUpdate(req_vehicle_liftgate=True))
    assert order2.req_vehicle_liftgate is True
    
    order3 = service.delete_order(con, "O1")
    assert order3.order_id == "O1"
    
    assert len(service.list_orders(con)) == 0

from fastapi import FastAPI
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_router_api(tmp_path):
    con = setup_db(tmp_path)
    con.execute("INSERT INTO locations (location_id, zip, city, latitude, longitude) VALUES (1, '1000', 'A', 1, 1)")
    
    from features.orders.router import get_db_con
    app.dependency_overrides[get_db_con] = lambda: con
    
    resp = client.post("/api/orders", json={"order_id": "O2", "destination_location_id": 1, "req_driver_adr": True})
    assert resp.status_code == 200
    assert resp.json()["order_id"] == "O2"
    
    resp = client.patch("/api/orders/O2", json={"req_vehicle_liftgate": True})
    assert resp.status_code == 200
    assert resp.json()["req_vehicle_liftgate"] is True
    
    resp = client.delete("/api/orders/O2")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

