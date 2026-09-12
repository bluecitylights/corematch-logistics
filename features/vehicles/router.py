from fastapi import APIRouter, Depends, HTTPException
from features.vehicles.schemas import Vehicle, VehicleCreate, VehicleUpdate
from features.vehicles.service import VehicleService, get_vehicle_service

router = APIRouter(prefix="/api", tags=["vehicles"])

@router.get("/vehicles", response_model=list[Vehicle])
async def list_vehicles_api(include_inactive: bool = False, service: VehicleService = Depends(get_vehicle_service)):
    return service.list_vehicles(include_inactive=include_inactive)

@router.post("/vehicles", response_model=Vehicle)
async def create_vehicle_api(payload: VehicleCreate, service: VehicleService = Depends(get_vehicle_service)):
    return service.create_vehicle(payload)

@router.patch("/vehicles/{vehicle_id}", response_model=Vehicle)
async def update_vehicle_api(vehicle_id: str, payload: VehicleUpdate, service: VehicleService = Depends(get_vehicle_service)):
    veh = service.update_vehicle(vehicle_id, payload)
    if veh is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return veh

@router.delete("/vehicles/{vehicle_id}", response_model=Vehicle)
async def delete_vehicle_api(vehicle_id: str, service: VehicleService = Depends(get_vehicle_service)):
    veh = service.delete_vehicle(vehicle_id)
    if veh is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return veh
