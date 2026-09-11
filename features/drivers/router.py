from fastapi import APIRouter, Depends, HTTPException
from typing import Sequence
import duckdb

from core.database import get_db
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate
from features.drivers import service

router = APIRouter(prefix="/api", tags=["drivers"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("/drivers", response_model=list[Driver])
async def list_drivers_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.list_drivers(con)

@router.post("/drivers", response_model=Driver)
async def create_driver_api(payload: DriverCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return service.create_driver(con, payload)

@router.patch("/drivers/{driver_id}", response_model=Driver)
async def update_driver_api(driver_id: str, payload: DriverUpdate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    drv = service.update_driver(con, driver_id, payload)
    if drv is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drv

@router.delete("/drivers/{driver_id}", response_model=Driver)
async def delete_driver_api(driver_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    drv = service.delete_driver(con, driver_id)
    if drv is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drv

