from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.debt import DebtIn, DebtOut
from app.services.debt_service import DebtService

router = APIRouter(prefix="/debts", tags=["debts"])


@router.get("", response_model=list[DebtOut])
def list_debts(user: CurrentUser, session: SessionDep) -> list[DebtOut]:
    service = DebtService(session)
    return [DebtOut.model_validate(d) for d in service.list(user.household_id)]


@router.post("", response_model=DebtOut, status_code=201)
def create_debt(payload: DebtIn, user: CurrentUser, session: SessionDep) -> DebtOut:
    service = DebtService(session)
    return DebtOut.model_validate(
        service.create(user.household_id, payload, actor_id=user.id)
    )


@router.put("/{debt_id}", response_model=DebtOut)
def update_debt(
    debt_id: int, payload: DebtIn, user: CurrentUser, session: SessionDep
) -> DebtOut:
    service = DebtService(session)
    return DebtOut.model_validate(
        service.update(user.household_id, debt_id, payload, actor_id=user.id)
    )


@router.delete("/{debt_id}", status_code=204)
def delete_debt(debt_id: int, user: CurrentUser, session: SessionDep) -> Response:
    DebtService(session).delete(user.household_id, debt_id)
    return Response(status_code=204)
