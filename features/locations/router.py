from fastapi import APIRouter, Depends, HTTPException
from features.locations.schemas import Location, LocationCreate, DistanceMatrixItem
from features.locations.service import LocationService, get_location_service

router = APIRouter(prefix="/api", tags=["locations"])

@router.get("/locations", response_model=list[Location])
async def list_locations_api(service: LocationService = Depends(get_location_service)):
    return service.list_locations()

@router.post("/locations", response_model=Location)
async def create_location_api(payload: LocationCreate, service: LocationService = Depends(get_location_service)):
    return service.create_location(payload)

@router.get("/distance-matrix/{origin_zip}", response_model=list[DistanceMatrixItem])
async def distance_matrix_api(origin_zip: str, service: LocationService = Depends(get_location_service)):
    rows = service.get_distance_matrix(origin_zip)
    if not rows:
        raise HTTPException(status_code=404, detail=f"Location not found: {origin_zip}")
    return list(rows)
