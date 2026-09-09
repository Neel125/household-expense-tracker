from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.investment import InvestmentDetailOut, InvestmentIn, InvestmentOut
from app.services.investment_service import InvestmentService
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/investments", tags=["investments"])


def _enriched(session, household_id: int, investment) -> InvestmentOut:
    """A holding is never returned bare: the linked contributions are what
    make its invested total and projected value meaningful."""
    _, view = PortfolioService(session).investment_view(household_id, investment.id)
    return InvestmentOut.of(investment, view)


@router.get("", response_model=list[InvestmentOut])
def list_investments(user: CurrentUser, session: SessionDep) -> list[InvestmentOut]:
    views = PortfolioService(session).investment_views(user.household_id)
    return [InvestmentOut.of(inv, view) for inv, view in views]


@router.get("/{investment_id}", response_model=InvestmentDetailOut)
def get_investment(
    investment_id: int, user: CurrentUser, session: SessionDep
) -> InvestmentDetailOut:
    """The holding plus every transaction that contributed to it."""
    inv, view = PortfolioService(session).investment_view(user.household_id, investment_id)
    return InvestmentDetailOut.of(inv, view)


@router.post("", response_model=InvestmentOut, status_code=201)
def create_investment(
    payload: InvestmentIn, user: CurrentUser, session: SessionDep
) -> InvestmentOut:
    inv = InvestmentService(session).create(user.household_id, payload, actor_id=user.id)
    return _enriched(session, user.household_id, inv)


@router.put("/{investment_id}", response_model=InvestmentOut)
def update_investment(
    investment_id: int,
    payload: InvestmentIn,
    user: CurrentUser,
    session: SessionDep,
) -> InvestmentOut:
    inv = InvestmentService(session).update(
        user.household_id, investment_id, payload, actor_id=user.id
    )
    return _enriched(session, user.household_id, inv)


@router.delete("/{investment_id}", status_code=204)
def delete_investment(
    investment_id: int, user: CurrentUser, session: SessionDep
) -> Response:
    InvestmentService(session).delete(user.household_id, investment_id, actor_id=user.id)
    return Response(status_code=204)
