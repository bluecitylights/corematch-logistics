from fastapi import APIRouter, Depends, HTTPException
from features.drivers.schemas import Driver, DriverCreate, DriverUpdate
from features.drivers.service import DriverService, get_driver_service

router = APIRouter(prefix="/api", tags=["drivers"])

@router.get("/drivers", response_model=list[Driver])
async def list_drivers_api(include_inactive: bool = False, service: DriverService = Depends(get_driver_service)):
    return service.list_drivers(include_inactive=include_inactive)

@router.post("/drivers", response_model=Driver)
async def create_driver_api(payload: DriverCreate, service: DriverService = Depends(get_driver_service)):
    return service.create_driver(payload)

@router.patch("/drivers/{driver_id}", response_model=Driver)
async def update_driver_api(driver_id: str, payload: DriverUpdate, service: DriverService = Depends(get_driver_service)):
    drv = service.update_driver(driver_id, payload)
    if drv is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drv

@router.delete("/drivers/{driver_id}", response_model=Driver)
async def delete_driver_api(driver_id: str, service: DriverService = Depends(get_driver_service)):
    drv = service.delete_driver(driver_id)
    if drv is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return drv
