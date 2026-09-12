import duckdb
from typing import Generator, Sequence
from core.base_service import BaseService
from core.database import get_db, query_models, execute_update, query_model_or_none
from features.orders.schemas import Order, OrderCreate, OrderUpdate


class OrderService(BaseService):
    """Domain service for managing customer orders."""

    def list_orders(self) -> Sequence[Order]:
        return query_models(Order, self.con, "SELECT * FROM orders ORDER BY order_id")

    def create_order(self, payload: OrderCreate) -> Order:
        self.con.execute(
            "INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.order_id, payload.destination_location_id, payload.req_driver_adr, payload.req_driver_ehbo, payload.req_vehicle_liftgate, payload.req_vehicle_refrigerated],
        )
        order = query_model_or_none(Order, self.con, "SELECT * FROM orders WHERE order_id = ?", [payload.order_id])
        if order is None:
            raise ValueError("Failed to retrieve created order")
        return order

    def update_order(self, order_id: str, payload: OrderUpdate) -> Order | None:
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return query_model_or_none(Order, self.con, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        execute_update("orders", "order_id", order_id, fields, con=self.con)
        return query_model_or_none(Order, self.con, "SELECT * FROM orders WHERE order_id = ?", [order_id])

    def delete_order(self, order_id: str) -> Order | None:
        order = query_model_or_none(Order, self.con, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        if order:
            self.con.execute("DELETE FROM orders WHERE order_id = ?", [order_id])
        return order

    def count(self) -> int:
        row = self.con.execute("SELECT COUNT(*) FROM orders").fetchone()
        return row[0] if row else 0


def get_order_service() -> Generator[OrderService, None, None]:
    with get_db() as con:
        yield OrderService(con)


order_service = OrderService()
