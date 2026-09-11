from fastapi import APIRouter, Depends, HTTPException
import duckdb

from core.database import get_db
from features.orders.schemas import Order, OrderCreate, OrderUpdate
from features.orders import service

router = APIRouter(prefix="/api/orders", tags=["orders"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("", response_model=list[Order])
async def list_orders_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.list_orders(con)

@router.post("", response_model=Order)
async def create_order_api(payload: OrderCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.create_order(con, payload)

@router.patch("/{order_id}", response_model=Order)
async def update_order_api(order_id: str, payload: OrderUpdate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    order = service.update_order(con, order_id, payload)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.delete("/{order_id}")
async def delete_order_api(order_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    order = service.delete_order(con, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    return {"status": "deleted"}

