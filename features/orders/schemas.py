from core.models import CoreMatchBaseModel

class OrderBase(CoreMatchBaseModel):
    req_driver_adr: bool = False
    req_driver_ehbo: bool = False
    req_vehicle_liftgate: bool = False
    req_vehicle_refrigerated: bool = False

class OrderCreate(OrderBase):
    order_id: str
    destination_location_id: int

class OrderUpdate(CoreMatchBaseModel):
    destination_location_id: int | None = None
    req_driver_adr: bool | None = None
    req_driver_ehbo: bool | None = None
    req_vehicle_liftgate: bool | None = None
    req_vehicle_refrigerated: bool | None = None

class Order(OrderCreate):
    order_index: int | None = None

