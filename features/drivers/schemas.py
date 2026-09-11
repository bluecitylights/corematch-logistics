from pydantic import Field
from core.models import CoreMatchBaseModel

class DriverBase(CoreMatchBaseModel):
    is_active: bool = True
    skill_adr: bool = False
    skill_ehbo: bool = False

class DriverCreate(DriverBase):
    driver_id: str
    location_id: int

class DriverUpdate(CoreMatchBaseModel):
    is_active: bool | None = None
    skill_adr: bool | None = None
    skill_ehbo: bool | None = None
    location_id: int | None = None

class Driver(DriverCreate):
    driver_index: int

