import duckdb
from typing import Generator, Sequence
from core.base_service import BaseService
from core.database import get_db
from features.orders.schemas import Order, OrderCreate, OrderUpdate


class OrderService(BaseService):
    """Domain service for managing customer orders."""

    def list_orders(self) -> Sequence[Order]:
        return self.query_models(Order, "SELECT * FROM orders ORDER BY order_id")

    def create_order(self, payload: OrderCreate) -> Order:
        self.execute(
            "INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.order_id, payload.destination_location_id, payload.req_driver_adr, payload.req_driver_ehbo, payload.req_vehicle_liftgate, payload.req_vehicle_refrigerated],
        )
        order = self.query_model_or_none(Order, "SELECT * FROM orders WHERE order_id = ?", [payload.order_id])
        if order is None:
            raise ValueError("Failed to retrieve created order")
        return order

    def update_order(self, order_id: str, payload: OrderUpdate) -> Order | None:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return self.query_model_or_none(Order, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        self.execute_update("orders", "order_id", order_id, fields)
        return self.query_model_or_none(Order, "SELECT * FROM orders WHERE order_id = ?", [order_id])

    def delete_order(self, order_id: str) -> Order | None:
        order = self.query_model_or_none(Order, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        if order:
            self.execute("DELETE FROM orders WHERE order_id = ?", [order_id])
        return order

    def count(self) -> int:
        rows = self.fetch_all("SELECT COUNT(*) FROM orders")
        return rows[0][0] if rows else 0


def get_order_service() -> Generator[OrderService, None, None]:
    with get_db() as con:
        yield OrderService(con)


order_service = OrderService()

list_orders = order_service.list_orders
create_order = order_service.create_order
update_order = order_service.update_order
delete_order = order_service.delete_order
count = order_service.count