import duckdb
from fastapi import APIRouter, Depends, HTTPException
from core.database import get_db
from features.orders.schemas import Order, OrderCreate, OrderUpdate
from features.orders.service import order_service

router = APIRouter(prefix="/api/orders", tags=["orders"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("", response_model=list[Order])
async def list_orders_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return order_service.list_orders(con=con)

@router.post("", response_model=Order)
async def create_order_api(payload: OrderCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return order_service.create_order(payload, con=con)

@router.patch("/{order_id}", response_model=Order)
async def update_order_api(order_id: str, payload: OrderUpdate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    order = order_service.update_order(order_id, payload, con=con)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.delete("/{order_id}")
async def delete_order_api(order_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    order = order_service.delete_order(order_id, con=con)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    return {"status": "deleted"}



