from typing import Optional

from app.schemas.base import CamelModel


class VehicleIn(CamelModel):
    name: str
    kind: str = "car"
    registration: str = ""
    make: str = ""
    model: str = ""
    year: int = 0
    color: str = ""
    fuel: str = "petrol"
    chassis_no: str = ""
    engine_no: str = ""
    purchase_date: str = ""
    odometer: int = 0
    notes: str = ""


class VehicleRecordIn(CamelModel):
    kind: str
    title: str = ""
    date: str = ""
    expiry_date: str = ""
    amount: float = 0
    vendor: str = ""
    reference: str = ""
    odometer: int = 0
    status: str = ""
    notes: str = ""


class VehicleRecordOut(CamelModel):
    id: int
    vehicle_id: int
    kind: str
    title: str = ""
    date: str = ""
    expiry_date: str = ""
    amount: float = 0
    vendor: str = ""
    reference: str = ""
    odometer: int = 0
    status: str = ""
    notes: str = ""
    days_left: Optional[int] = None
    created_at: str = ""
    updated_at: Optional[str] = None


class PaperStatus(CamelModel):
    expiry_date: str = ""
    days_left: Optional[int] = None
    title: str = ""
    reference: str = ""


class VehicleOut(CamelModel):
    id: int
    name: str
    kind: str
    registration: str = ""
    make: str = ""
    model: str = ""
    year: int = 0
    color: str = ""
    fuel: str = "petrol"
    chassis_no: str = ""
    engine_no: str = ""
    purchase_date: str = ""
    odometer: int = 0
    notes: str = ""
    insurance: Optional[PaperStatus] = None
    puc: Optional[PaperStatus] = None
    rc: Optional[PaperStatus] = None
    fitness: Optional[PaperStatus] = None
    unpaid_challans: int = 0
    unpaid_challan_amount: float = 0
    last_service_date: str = ""
    last_service_odometer: int = 0
    alert_count: int = 0
    records: list[VehicleRecordOut] = []
    created_at: str = ""
    updated_at: Optional[str] = None
