from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.investment import InvestmentIn, InvestmentOut
from app.services.investment_service import InvestmentService

router = APIRouter(prefix="/investments", tags=["investments"])


@router.get("", response_model=list[InvestmentOut])
def list_investments(user: CurrentUser, session: SessionDep) -> list[InvestmentOut]:
    service = InvestmentService(session)
    return [InvestmentOut.model_validate(i) for i in service.list(user.household_id)]


@router.post("", response_model=InvestmentOut, status_code=201)
def create_investment(
    payload: InvestmentIn, user: CurrentUser, session: SessionDep
) -> InvestmentOut:
    service = InvestmentService(session)
    return InvestmentOut.model_validate(
        service.create(user.household_id, payload, actor_id=user.id)
    )


@router.put("/{investment_id}", response_model=InvestmentOut)
def update_investment(
    investment_id: int,
    payload: InvestmentIn,
    user: CurrentUser,
    session: SessionDep,
) -> InvestmentOut:
    service = InvestmentService(session)
    return InvestmentOut.model_validate(
        service.update(user.household_id, investment_id, payload, actor_id=user.id)
    )


@router.delete("/{investment_id}", status_code=204)
def delete_investment(
    investment_id: int, user: CurrentUser, session: SessionDep
) -> Response:
    InvestmentService(session).delete(user.household_id, investment_id, actor_id=user.id)
    return Response(status_code=204)
