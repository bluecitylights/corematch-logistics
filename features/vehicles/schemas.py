from core.models import CoreMatchBaseModel

class VehicleBase(CoreMatchBaseModel):
    is_active: bool = True
    spec_liftgate: bool = False
    spec_refrigerated: bool = False

class VehicleCreate(VehicleBase):
    vehicle_id: str
    license_plate: str
    location_id: int

class VehicleUpdate(CoreMatchBaseModel):
    is_active: bool | None = None
    spec_liftgate: bool | None = None
    spec_refrigerated: bool | None = None
    license_plate: str | None = None
    location_id: int | None = None

class Vehicle(VehicleCreate):
    vehicle_index: int

