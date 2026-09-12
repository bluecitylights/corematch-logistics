import duckdb
from typing import Sequence
from core.database import query_models, execute_update, query_model_or_none
from features.orders.schemas import Order, OrderCreate, OrderUpdate

def list_orders(con: duckdb.DuckDBPyConnection) -> Sequence[Order]:
    return query_models(Order, con, "SELECT * FROM orders ORDER BY order_id")

def create_order(con: duckdb.DuckDBPyConnection, payload: OrderCreate) -> Order:
    con.execute(
        "INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
        [payload.order_id, payload.destination_location_id, payload.req_driver_adr, payload.req_driver_ehbo, payload.req_vehicle_liftgate, payload.req_vehicle_refrigerated],
    )
    order = query_model_or_none(Order, con, "SELECT * FROM orders WHERE order_id = ?", [payload.order_id])
    if order is None:
        raise ValueError("Failed to retrieve created order")
    return order

def update_order(con: duckdb.DuckDBPyConnection, order_id: str, payload: OrderUpdate) -> Order | None:
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return query_model_or_none(Order, con, "SELECT * FROM orders WHERE order_id = ?", [order_id])
    
    execute_update("orders", "order_id", order_id, fields, con=con)
    return query_model_or_none(Order, con, "SELECT * FROM orders WHERE order_id = ?", [order_id])

def delete_order(con: duckdb.DuckDBPyConnection, order_id: str) -> Order | None:
    order = query_model_or_none(Order, con, "SELECT * FROM orders WHERE order_id = ?", [order_id])
    if order:
        con.execute("DELETE FROM orders WHERE order_id = ?", [order_id])
    return order

