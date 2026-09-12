from fastapi import APIRouter, Depends, HTTPException
from features.orders.schemas import Order, OrderCreate, OrderUpdate
from features.orders.service import OrderService, get_order_service

router = APIRouter(prefix="/api/orders", tags=["orders"])

@router.get("", response_model=list[Order])
async def list_orders_api(service: OrderService = Depends(get_order_service)):
    return service.list_orders()

@router.post("", response_model=Order)
async def create_order_api(payload: OrderCreate, service: OrderService = Depends(get_order_service)):
    return service.create_order(payload)

@router.patch("/{order_id}", response_model=Order)
async def update_order_api(order_id: str, payload: OrderUpdate, service: OrderService = Depends(get_order_service)):
    order = service.update_order(order_id, payload)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.delete("/{order_id}")
async def delete_order_api(order_id: str, service: OrderService = Depends(get_order_service)):
    order = service.delete_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail=f"Order not found: {order_id}")
    return {"status": "deleted"}
