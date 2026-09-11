from fastapi import APIRouter, Depends, HTTPException
import duckdb

from core.database import get_db
from features.vehicles.schemas import Vehicle, VehicleCreate, VehicleUpdate
from features.vehicles import service

router = APIRouter(prefix="/api", tags=["vehicles"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("/vehicles", response_model=list[Vehicle])
async def list_vehicles_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.list_vehicles(con)

@router.post("/vehicles", response_model=Vehicle)
async def create_vehicle_api(payload: VehicleCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.create_vehicle(con, payload)

@router.patch("/vehicles/{vehicle_id}", response_model=Vehicle)
async def update_vehicle_api(vehicle_id: str, payload: VehicleUpdate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    veh = service.update_vehicle(con, vehicle_id, payload)
    if veh is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return veh

@router.delete("/vehicles/{vehicle_id}", response_model=Vehicle)
async def delete_vehicle_api(vehicle_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    veh = service.delete_vehicle(con, vehicle_id)
    if veh is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return veh

