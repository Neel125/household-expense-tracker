from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.income import IncomeSourceIn, IncomeSourceOut
from app.services.income_service import IncomeService

router = APIRouter(prefix="/income-sources", tags=["income"])


@router.get("", response_model=list[IncomeSourceOut])
def list_income(user: CurrentUser, session: SessionDep) -> list[IncomeSourceOut]:
    service = IncomeService(session)
    return [IncomeSourceOut.model_validate(s) for s in service.list(user.household_id)]


@router.post("", response_model=IncomeSourceOut, status_code=201)
def create_income(payload: IncomeSourceIn, user: CurrentUser, session: SessionDep) -> IncomeSourceOut:
    service = IncomeService(session)
    return IncomeSourceOut.model_validate(service.create(user.household_id, payload))


@router.put("/{source_id}", response_model=IncomeSourceOut)
def update_income(source_id: int, payload: IncomeSourceIn, user: CurrentUser, session: SessionDep) -> IncomeSourceOut:
    service = IncomeService(session)
    return IncomeSourceOut.model_validate(service.update(user.household_id, source_id, payload))


@router.delete("/{source_id}", status_code=204)
def delete_income(source_id: int, user: CurrentUser, session: SessionDep) -> Response:
    IncomeService(session).delete(user.household_id, source_id)
    return Response(status_code=204)
