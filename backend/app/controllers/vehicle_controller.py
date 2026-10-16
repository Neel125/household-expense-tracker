from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.vehicle import VehicleIn, VehicleOut, VehicleRecordIn
from app.services.vehicle_service import VehicleService

router = APIRouter(prefix="/vehicles", tags=["garage"])


@router.get("", response_model=list[VehicleOut])
def list_vehicles(user: CurrentUser, session: SessionDep) -> list[VehicleOut]:
    return VehicleService(session).list(user.household_id)


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(payload: VehicleIn, user: CurrentUser, session: SessionDep) -> VehicleOut:
    return VehicleService(session).create(user.household_id, payload)


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, user: CurrentUser, session: SessionDep) -> VehicleOut:
    return VehicleService(session).get(user.household_id, vehicle_id)


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(
    vehicle_id: int, payload: VehicleIn, user: CurrentUser, session: SessionDep
) -> VehicleOut:
    return VehicleService(session).update(user.household_id, vehicle_id, payload)


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int, user: CurrentUser, session: SessionDep) -> Response:
    VehicleService(session).delete(user.household_id, vehicle_id)
    return Response(status_code=204)


@router.post("/{vehicle_id}/records", response_model=VehicleOut, status_code=201)
def add_record(
    vehicle_id: int, payload: VehicleRecordIn, user: CurrentUser, session: SessionDep
) -> VehicleOut:
    return VehicleService(session).add_record(user.household_id, vehicle_id, payload)


@router.put("/{vehicle_id}/records/{record_id}", response_model=VehicleOut)
def update_record(
    vehicle_id: int,
    record_id: int,
    payload: VehicleRecordIn,
    user: CurrentUser,
    session: SessionDep,
) -> VehicleOut:
    return VehicleService(session).update_record(user.household_id, vehicle_id, record_id, payload)


@router.delete("/{vehicle_id}/records/{record_id}", response_model=VehicleOut)
def delete_record(
    vehicle_id: int, record_id: int, user: CurrentUser, session: SessionDep
) -> VehicleOut:
    return VehicleService(session).delete_record(user.household_id, vehicle_id, record_id)
