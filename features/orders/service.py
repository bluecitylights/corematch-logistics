import duckdb
from typing import Any, Generator, Sequence
from core.base_service import BaseService
from core.database import get_db, query_models, execute_update, query_model_or_none
from features.orders.schemas import Order, OrderCreate, OrderUpdate


class OrderService(BaseService):
    """Domain service for managing customer orders."""

    def list_orders(self, con: duckdb.DuckDBPyConnection | None = None) -> Sequence[Order]:
        c = con or self.con
        return query_models(Order, c, "SELECT * FROM orders ORDER BY order_id")

    def create_order(self, arg1: Any, arg2: Any = None) -> Order:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
            payload = arg2
        else:
            c = self.con
            payload = arg1
        c.execute(
            "INSERT INTO orders (order_id, destination_location_id, req_driver_adr, req_driver_ehbo, req_vehicle_liftgate, req_vehicle_refrigerated) VALUES (?, ?, ?, ?, ?, ?)",
            [payload.order_id, payload.destination_location_id, payload.req_driver_adr, payload.req_driver_ehbo, payload.req_vehicle_liftgate, payload.req_vehicle_refrigerated],
        )
        order = query_model_or_none(Order, c, "SELECT * FROM orders WHERE order_id = ?", [payload.order_id])
        if order is None:
            raise ValueError("Failed to retrieve created order")
        return order

    def update_order(self, arg1: Any, arg2: Any, arg3: Any = None) -> Order | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
            order_id = arg2
            payload = arg3
        else:
            c = self.con
            order_id = arg1
            payload = arg2
        fields = payload.model_dump(exclude_unset=True)
        if not fields:
            return query_model_or_none(Order, c, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        execute_update("orders", "order_id", order_id, fields, con=c)
        return query_model_or_none(Order, c, "SELECT * FROM orders WHERE order_id = ?", [order_id])

    def delete_order(self, arg1: Any, arg2: Any = None) -> Order | None:
        if isinstance(arg1, duckdb.DuckDBPyConnection):
            c = arg1
            order_id = arg2
        else:
            c = self.con
            order_id = arg1
        order = query_model_or_none(Order, c, "SELECT * FROM orders WHERE order_id = ?", [order_id])
        if order:
            c.execute("DELETE FROM orders WHERE order_id = ?", [order_id])
        return order

    def count(self, con: duckdb.DuckDBPyConnection | None = None) -> int:
        c = con or self.con
        row = c.execute("SELECT COUNT(*) FROM orders").fetchone()
        return row[0] if row else 0


def get_order_service() -> Generator[OrderService, None, None]:
    with get_db() as con:
        yield OrderService(con)


order_service = OrderService()

# Backward-compatibility aliases
list_orders = order_service.list_orders
create_order = order_service.create_order
update_order = order_service.update_order
delete_order = order_service.delete_order
count = order_service.count
