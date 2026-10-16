"""Household vehicles and the papers / service / challans on them."""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlmodel import Session

from app.models.mixins import now_iso
from app.models.vehicle import (
    CHALLAN_STATUSES,
    FUELS,
    RECORD_KINDS,
    VEHICLE_KINDS,
    Vehicle,
    VehicleRecord,
)
from app.repositories.repositories import VehicleRecordRepository, VehicleRepository
from app.schemas.vehicle import (
    PaperStatus,
    VehicleIn,
    VehicleOut,
    VehicleRecordIn,
    VehicleRecordOut,
)
from app.services.errors import NotFoundError, ValidationError

ALERT_DAYS = 30


def _days_left(iso: str) -> Optional[int]:
    if not iso:
        return None
    try:
        due = date.fromisoformat(iso[:10])
    except ValueError:
        return None
    return (due - date.today()).days


def _paper(records: list[VehicleRecord], kind: str) -> Optional[PaperStatus]:
    dated = [r for r in records if r.kind == kind and r.expiry_date]
    if not dated:
        return None
    latest = max(dated, key=lambda r: r.expiry_date)
    return PaperStatus(
        expiry_date=latest.expiry_date,
        days_left=_days_left(latest.expiry_date),
        title=latest.title,
        reference=latest.reference,
    )


def _record_out(row: VehicleRecord) -> VehicleRecordOut:
    return VehicleRecordOut(
        id=row.id,
        vehicle_id=row.vehicle_id,
        kind=row.kind,
        title=row.title,
        date=row.date,
        expiry_date=row.expiry_date,
        amount=row.amount,
        vendor=row.vendor,
        reference=row.reference,
        odometer=row.odometer,
        status=row.status,
        notes=row.notes,
        days_left=_days_left(row.expiry_date),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _default_title(kind: str) -> str:
    return {
        "maintenance": "Service",
        "insurance": "Insurance",
        "puc": "PUC",
        "rc": "RC",
        "challan": "Challan",
        "fitness": "Fitness",
        "other": "Record",
    }.get(kind, "Record")


class VehicleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.vehicles = VehicleRepository(session)
        self.records = VehicleRecordRepository(session)

    def list(self, household_id: int) -> list[VehicleOut]:
        vehicles = list(self.vehicles.list(household_id))
        grouped: dict[int, list[VehicleRecord]] = {v.id: [] for v in vehicles}
        for row in self.records.list(household_id):
            grouped.setdefault(row.vehicle_id, []).append(row)
        return [self._out(v, grouped.get(v.id, [])) for v in vehicles]

    def get(self, household_id: int, vehicle_id: int) -> VehicleOut:
        vehicle = self.vehicles.get(household_id, vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle not found")
        return self._out(vehicle, list(self.records.for_vehicle(household_id, vehicle_id)))

    def create(self, household_id: int, data: VehicleIn) -> VehicleOut:
        vehicle = self.vehicles.add(self._apply(Vehicle(household_id=household_id), data, creating=True))
        return self._out(vehicle, [])

    def update(self, household_id: int, vehicle_id: int, data: VehicleIn) -> VehicleOut:
        vehicle = self.vehicles.get(household_id, vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle not found")
        vehicle = self.vehicles.save(self._apply(vehicle, data, creating=False))
        return self._out(vehicle, list(self.records.for_vehicle(household_id, vehicle_id)))

    def delete(self, household_id: int, vehicle_id: int) -> None:
        vehicle = self.vehicles.get(household_id, vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle not found")
        self.records.delete_for_vehicle(household_id, vehicle_id)
        self.vehicles.delete(vehicle)

    def add_record(self, household_id: int, vehicle_id: int, data: VehicleRecordIn) -> VehicleOut:
        vehicle = self.vehicles.get(household_id, vehicle_id)
        if not vehicle:
            raise NotFoundError("Vehicle not found")
        row = self._apply_record(
            VehicleRecord(household_id=household_id, vehicle_id=vehicle_id),
            data,
            creating=True,
        )
        self.records.add(row)
        if row.kind == "maintenance" and row.odometer > vehicle.odometer:
            vehicle.odometer = row.odometer
            vehicle.updated_at = now_iso()
            self.vehicles.save(vehicle)
        return self.get(household_id, vehicle_id)

    def update_record(
        self, household_id: int, vehicle_id: int, record_id: int, data: VehicleRecordIn
    ) -> VehicleOut:
        if not self.vehicles.get(household_id, vehicle_id):
            raise NotFoundError("Vehicle not found")
        row = self.records.get(household_id, record_id)
        if not row or row.vehicle_id != vehicle_id:
            raise NotFoundError("Record not found")
        self.records.save(self._apply_record(row, data, creating=False))
        return self.get(household_id, vehicle_id)

    def delete_record(self, household_id: int, vehicle_id: int, record_id: int) -> VehicleOut:
        if not self.vehicles.get(household_id, vehicle_id):
            raise NotFoundError("Vehicle not found")
        row = self.records.get(household_id, record_id)
        if not row or row.vehicle_id != vehicle_id:
            raise NotFoundError("Record not found")
        self.records.delete(row)
        return self.get(household_id, vehicle_id)

    def _apply(self, vehicle: Vehicle, data: VehicleIn, creating: bool) -> Vehicle:
        name = (data.name or "").strip()
        if not name:
            raise ValidationError("A vehicle needs a name")
        kind = (data.kind or "car").strip().lower()
        if kind not in VEHICLE_KINDS:
            raise ValidationError("Unknown vehicle type")
        fuel = (data.fuel or "petrol").strip().lower()
        if fuel not in FUELS:
            raise ValidationError("Unknown fuel type")
        vehicle.name = name
        vehicle.kind = kind
        vehicle.registration = (data.registration or "").strip().upper()
        vehicle.make = (data.make or "").strip()
        vehicle.model = (data.model or "").strip()
        vehicle.year = max(0, int(data.year or 0))
        vehicle.color = (data.color or "").strip()
        vehicle.fuel = fuel
        vehicle.chassis_no = (data.chassis_no or "").strip()
        vehicle.engine_no = (data.engine_no or "").strip()
        vehicle.purchase_date = (data.purchase_date or "").strip()
        vehicle.odometer = max(0, int(data.odometer or 0))
        vehicle.notes = (data.notes or "").strip()
        if creating:
            vehicle.created_at = now_iso()
        else:
            vehicle.updated_at = now_iso()
        return vehicle

    def _apply_record(self, row: VehicleRecord, data: VehicleRecordIn, creating: bool) -> VehicleRecord:
        kind = (data.kind or "").strip().lower()
        if kind not in RECORD_KINDS:
            raise ValidationError("Unknown record type")
        status = (data.status or "").strip().lower()
        if kind == "challan":
            if status not in CHALLAN_STATUSES:
                status = "unpaid"
        else:
            status = status if status in ("", "open", "closed") else ""
        row.kind = kind
        row.title = (data.title or "").strip() or _default_title(kind)
        row.date = (data.date or "").strip()
        row.expiry_date = (data.expiry_date or "").strip()
        row.amount = max(0.0, float(data.amount or 0))
        row.vendor = (data.vendor or "").strip()
        row.reference = (data.reference or "").strip()
        row.odometer = max(0, int(data.odometer or 0))
        row.status = status
        row.notes = (data.notes or "").strip()
        if creating:
            row.created_at = now_iso()
        else:
            row.updated_at = now_iso()
        return row

    def _out(self, vehicle: Vehicle, records: list[VehicleRecord]) -> VehicleOut:
        records = sorted(records, key=lambda r: (r.date or "", r.id or 0), reverse=True)
        unpaid = [r for r in records if r.kind == "challan" and r.status != "paid"]
        services = [r for r in records if r.kind == "maintenance"]
        last = services[0] if services else None
        papers = {
            "insurance": _paper(records, "insurance"),
            "puc": _paper(records, "puc"),
            "rc": _paper(records, "rc"),
            "fitness": _paper(records, "fitness"),
        }
        alerts = sum(
            1
            for p in papers.values()
            if p and p.days_left is not None and p.days_left <= ALERT_DAYS
        ) + len(unpaid)
        return VehicleOut(
            id=vehicle.id,
            name=vehicle.name,
            kind=vehicle.kind,
            registration=vehicle.registration,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            color=vehicle.color,
            fuel=vehicle.fuel,
            chassis_no=vehicle.chassis_no,
            engine_no=vehicle.engine_no,
            purchase_date=vehicle.purchase_date,
            odometer=vehicle.odometer,
            notes=vehicle.notes,
            insurance=papers["insurance"],
            puc=papers["puc"],
            rc=papers["rc"],
            fitness=papers["fitness"],
            unpaid_challans=len(unpaid),
            unpaid_challan_amount=sum(r.amount for r in unpaid),
            last_service_date=last.date if last else "",
            last_service_odometer=last.odometer if last else 0,
            alert_count=alerts,
            records=[_record_out(r) for r in records],
            created_at=vehicle.created_at,
            updated_at=vehicle.updated_at,
        )
