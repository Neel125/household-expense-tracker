from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.models.transaction import TYPE_INVESTMENT_WITHDRAWAL
from app.repositories.repositories import TransactionRepository
from app.schemas.investment import (
    InvestmentDetailOut,
    InvestmentIn,
    InvestmentOut,
    InvestmentReinvestIn,
    InvestmentReinvestOut,
    InvestmentWithdrawIn,
    LedgerEntryOut,
)
from app.services.investment_service import InvestmentService
from app.services.portfolio_math import by_date
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
    """The holding, its contributions, and the in/out ledger (including
    the auto-logged withdrawal or add-on)."""
    inv, view = PortfolioService(session).investment_view(user.household_id, investment_id)
    rows = TransactionRepository(session).ledger_for_investment(
        user.household_id, investment_id
    )
    ledger = [
        LedgerEntryOut(
            transaction_id=txn.id or 0,
            date=txn.date or "",
            name=txn.name or "",
            amount=max(0.0, float(txn.amount or 0)),
            kind="withdrawal" if txn.type == TYPE_INVESTMENT_WITHDRAWAL else "contribution",
            provider_type=txn.provider_type or "",
        )
        for txn in by_date(rows)
    ]
    return InvestmentDetailOut.of(inv, view, ledger)


@router.post("", response_model=InvestmentOut, status_code=201)
def create_investment(
    payload: InvestmentIn, user: CurrentUser, session: SessionDep
) -> InvestmentOut:
    inv = InvestmentService(session).create(user.household_id, payload, actor_id=user.id)
    return _enriched(session, user.household_id, inv)


@router.post("/{investment_id}/withdraw", response_model=InvestmentOut)
def withdraw_investment(
    investment_id: int,
    payload: InvestmentWithdrawIn,
    user: CurrentUser,
    session: SessionDep,
) -> InvestmentOut:
    """Close the holding and credit the proceeds to a bank account."""
    inv = InvestmentService(session).withdraw(
        user.household_id, investment_id, payload, actor_id=user.id
    )
    return _enriched(session, user.household_id, inv)


@router.post("/{investment_id}/reinvest", response_model=InvestmentReinvestOut)
def reinvest_investment(
    investment_id: int,
    payload: InvestmentReinvestIn,
    user: CurrentUser,
    session: SessionDep,
) -> InvestmentReinvestOut:
    """Close the holding and open a successor. Only the add-on is logged
    as an Investment transaction; the matured amount becomes the new
    opening invested."""
    closed, created = InvestmentService(session).reinvest(
        user.household_id, investment_id, payload, actor_id=user.id
    )
    return InvestmentReinvestOut(
        closed=_enriched(session, user.household_id, closed),
        created=_enriched(session, user.household_id, created),
    )


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
