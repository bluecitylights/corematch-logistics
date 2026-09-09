"""FastMCP tools that call the CoreMatch REST API."""

import os
from typing import Any

import httpx
from fastmcp import FastMCP


API_BASE_URL = os.environ.get("COREMATCH_API_URL", "http://127.0.0.1:8000").rstrip("/")
mcp = FastMCP("CoreMatch-Logistics")


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    response = httpx.request(
        method,
        f"{API_BASE_URL}{path}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool
def list_drivers(include_inactive: bool = False) -> list[dict[str, Any]]:
    """List drivers through the CoreMatch REST API."""
    return _request("GET", f"/api/drivers?include_inactive={include_inactive}")


@mcp.tool
def create_driver(driver_id: str, location: str, skill_adr: bool = False, skill_ehbo: bool = False) -> dict[str, Any]:
    """Create a driver through the CoreMatch REST API."""
    return _request("POST", "/api/drivers", locals())


@mcp.tool
def update_driver(driver_id: str, location: str | None = None, is_active: bool | None = None, skill_adr: bool | None = None, skill_ehbo: bool | None = None) -> dict[str, Any]:
    """Update a driver through the CoreMatch REST API."""
    return _request("PATCH", f"/api/drivers/{driver_id}", {key: value for key, value in locals().items() if key != "driver_id" and value is not None})


@mcp.tool
def delete_driver(driver_id: str) -> dict[str, Any]:
    """Deactivate a driver through the CoreMatch REST API."""
    return _request("DELETE", f"/api/drivers/{driver_id}")


@mcp.tool
def list_vehicles(include_inactive: bool = False) -> list[dict[str, Any]]:
    """List vehicles through the CoreMatch REST API."""
    return _request("GET", f"/api/vehicles?include_inactive={include_inactive}")


@mcp.tool
def create_vehicle(vehicle_id: str, license_plate: str, location: str, spec_liftgate: bool = False, spec_refrigerated: bool = False) -> dict[str, Any]:
    """Create a vehicle through the CoreMatch REST API."""
    return _request("POST", "/api/vehicles", locals())


@mcp.tool
def update_vehicle(vehicle_id: str, license_plate: str | None = None, location: str | None = None, is_active: bool | None = None, spec_liftgate: bool | None = None, spec_refrigerated: bool | None = None) -> dict[str, Any]:
    """Update a vehicle through the CoreMatch REST API."""
    return _request("PATCH", f"/api/vehicles/{vehicle_id}", {key: value for key, value in locals().items() if key != "vehicle_id" and value is not None})


@mcp.tool
def delete_vehicle(vehicle_id: str) -> dict[str, Any]:
    """Deactivate a vehicle through the CoreMatch REST API."""
    return _request("DELETE", f"/api/vehicles/{vehicle_id}")


@mcp.tool
def list_orders() -> list[dict[str, Any]]:
    """List orders through the CoreMatch REST API."""
    return _request("GET", "/api/orders")


@mcp.tool
def create_order(order_id: str, destination: str, req_driver_adr: bool = False, req_driver_ehbo: bool = False, req_vehicle_liftgate: bool = False, req_vehicle_refrigerated: bool = False) -> dict[str, Any]:
    """Create an order through the CoreMatch REST API."""
    return _request("POST", "/api/orders", locals())


@mcp.tool
def update_order(order_id: str, destination: str | None = None, req_driver_adr: bool | None = None, req_driver_ehbo: bool | None = None, req_vehicle_liftgate: bool | None = None, req_vehicle_refrigerated: bool | None = None) -> dict[str, Any]:
    """Update an order through the CoreMatch REST API."""
    return _request("PATCH", f"/api/orders/{order_id}", {key: value for key, value in locals().items() if key != "order_id" and value is not None})


@mcp.tool
def delete_order(order_id: str) -> dict[str, Any]:
    """Delete an order through the CoreMatch REST API."""
    return _request("DELETE", f"/api/orders/{order_id}")


@mcp.tool
def run_matching() -> list[dict[str, Any]]:
    """Run matching through the CoreMatch REST API."""
    return _request("POST", "/api/match")


if __name__ == "__main__":
    mcp.run()
