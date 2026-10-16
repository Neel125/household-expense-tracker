from typing import Optional

from sqlmodel import Field, SQLModel

VEHICLE_KINDS = ("car", "bike", "scooter", "other")
FUELS = ("petrol", "diesel", "cng", "ev", "hybrid")
RECORD_KINDS = ("maintenance", "insurance", "puc", "rc", "challan", "fitness", "other")
CHALLAN_STATUSES = ("unpaid", "paid", "contested")


class Vehicle(SQLModel, table=True):
    """A household vehicle. Papers, service and challans live on
    VehicleRecord so the car itself stays a thin identity."""

    __tablename__ = "vehicle"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
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
    created_at: str = ""
    updated_at: Optional[str] = None


class VehicleRecord(SQLModel, table=True):
    """One dated event on a vehicle: a service, a policy, PUC, RC
    renewal, or a challan."""

    __tablename__ = "vehicle_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    vehicle_id: int = Field(index=True, foreign_key="vehicle.id")
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
    created_at: str = ""
    updated_at: Optional[str] = None
