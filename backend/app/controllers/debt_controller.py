from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.debt import DebtIn, DebtOut, DebtScheduleOut
from app.services.debt_service import DebtService
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/debts", tags=["debts"])


def _enriched(session, household_id: int, debt) -> DebtOut:
    """`outstandingNow` only exists once the linked EMIs have been
    amortised, so every response goes through the portfolio read model."""
    _, view = PortfolioService(session).debt_view(household_id, debt.id)
    return DebtOut.of(debt, view)


@router.get("", response_model=list[DebtOut])
def list_debts(user: CurrentUser, session: SessionDep) -> list[DebtOut]:
    views = PortfolioService(session).debt_views(user.household_id)
    return [DebtOut.of(debt, view) for debt, view in views]


@router.get("/{debt_id}/schedule", response_model=DebtScheduleOut)
def get_debt_schedule(
    debt_id: int, user: CurrentUser, session: SessionDep
) -> DebtScheduleOut:
    """Every EMI logged against this loan, split into interest and
    principal on the reducing balance."""
    debt, view = PortfolioService(session).debt_view(user.household_id, debt_id)
    return DebtScheduleOut.of(debt, view)


@router.post("", response_model=DebtOut, status_code=201)
def create_debt(payload: DebtIn, user: CurrentUser, session: SessionDep) -> DebtOut:
    debt = DebtService(session).create(user.household_id, payload, actor_id=user.id)
    return _enriched(session, user.household_id, debt)


@router.put("/{debt_id}", response_model=DebtOut)
def update_debt(
    debt_id: int, payload: DebtIn, user: CurrentUser, session: SessionDep
) -> DebtOut:
    debt = DebtService(session).update(user.household_id, debt_id, payload, actor_id=user.id)
    return _enriched(session, user.household_id, debt)


@router.delete("/{debt_id}", status_code=204)
def delete_debt(debt_id: int, user: CurrentUser, session: SessionDep) -> Response:
    DebtService(session).delete(user.household_id, debt_id)
    return Response(status_code=204)
