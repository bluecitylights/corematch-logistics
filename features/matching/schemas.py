from core.models import CoreMatchBaseModel

class MatchResult(CoreMatchBaseModel):
    order_id: str
    assigned_driver: str | None = None
    assigned_vehicle: str | None = None
    status: str

