import duckdb
from fastapi import APIRouter, Depends, HTTPException
from core.database import get_db
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate
from features.drivers.service import driver_service

router = APIRouter(prefix="/api", tags=["drivers"])

def get_db_con():
    with get_db() as con:
        yield con

@router.get("/drivers", response_model=list[Driver])
async def list_drivers_api(con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return driver_service.list_drivers(con=con)

@router.post("/drivers", response_model=Driver)
async def create_driver_api(payload: DriverCreate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    return driver_service.create_driver(payload, con=con)

@router.patch("/drivers/{driver_id}", response_model=Driver)
async def update_driver_api(driver_id: str, payload: DriverUpdate, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    drv = driver_service.update_driver(driver_id, payload, con=con)
    if drv is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drv

@router.delete("/drivers/{driver_id}", response_model=Driver)
async def delete_driver_api(driver_id: str, con: duckdb.DuckDBPyConnection = Depends(get_db_con)):
    drv = driver_service.delete_driver(driver_id, con=con)
    if drv is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drv



