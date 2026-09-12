from core.models import CoreMatchBaseModel

class LocationBase(CoreMatchBaseModel):
    zip: str
    city: str
    latitude: float
    longitude: float

class LocationCreate(LocationBase):
    pass

class Location(LocationBase):
    location_id: int

class DistanceMatrixItem(CoreMatchBaseModel):
    origin_zip: str
    dest_zip: str
    distance_m: int
    travel_time_min: int

