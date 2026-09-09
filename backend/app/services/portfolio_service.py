"""The portfolio read model: holdings with their linked transactions applied.

`InvestmentService` and `DebtService` still own writing a holding's own
fields. This service owns the *joined* picture — what the linked
transactions make each holding worth — and is the single place that
answers it, so the portfolio page, the rewards engine and the debt
schedule endpoint can never disagree about an outstanding balance.

Nothing here writes. Every figure is recomputed from the transactions on
each read (see services.portfolio_math for why), which is affordable
because a household's linked rows are few and fetched in one query.
"""
from datetime import date
from typing import Optional

from sqlmodel import Session

from app.models import Debt, Investment, Transaction
from app.repositories.repositories import (
    DebtRepository,
    InvestmentRepository,
    TransactionRepository,
)
from app.services import portfolio_math
from app.services.errors import NotFoundError, ValidationError
from app.services.portfolio_math import DebtView, InvestmentView

# Which transaction type may link to what. The form enforces this too,
# but the rule lives here so the API can't be talked into an EMI that
# pays down a mutual fund.
LINK_TYPE_FOR_INVESTMENT = "Investment"
LINK_TYPE_FOR_DEBT = "Loan"


class PortfolioService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.investments = InvestmentRepository(session)
        self.debts = DebtRepository(session)
        self.transactions = TransactionRepository(session)

    # ------------------------------------------------------------ grouping
    def _grouped(self, household_id: int) -> tuple[dict[int, list], dict[int, list]]:
        by_investment: dict[int, list[Transaction]] = {}
        by_debt: dict[int, list[Transaction]] = {}
        for txn in self.transactions.portfolio_linked(household_id):
            if txn.type == LINK_TYPE_FOR_INVESTMENT and txn.investment_id:
                by_investment.setdefault(txn.investment_id, []).append(txn)
            elif txn.type == LINK_TYPE_FOR_DEBT and txn.debt_id:
                by_debt.setdefault(txn.debt_id, []).append(txn)
        return by_investment, by_debt

    # --------------------------------------------------------- investments
    def investment_views(
        self, household_id: int, today: Optional[date] = None
    ) -> list[tuple[Investment, InvestmentView]]:
        by_investment, _ = self._grouped(household_id)
        return [
            (inv, portfolio_math.view_investment(inv, by_investment.get(inv.id, []), today))
            for inv in self.investments.list(household_id)
        ]

    def investment_view(
        self, household_id: int, investment_id: int, today: Optional[date] = None
    ) -> tuple[Investment, InvestmentView]:
        inv = self.investments.get(household_id, investment_id)
        if not inv:
            raise NotFoundError("Investment not found")
        linked = self.transactions.for_investment(household_id, investment_id)
        return inv, portfolio_math.view_investment(inv, linked, today)

    # --------------------------------------------------------------- debts
    def debt_views(
        self, household_id: int, today: Optional[date] = None
    ) -> list[tuple[Debt, DebtView]]:
        _, by_debt = self._grouped(household_id)
        return [
            (debt, portfolio_math.view_debt(debt, by_debt.get(debt.id, []), today))
            for debt in self.debts.list(household_id)
        ]

    def debt_view(
        self, household_id: int, debt_id: int, today: Optional[date] = None
    ) -> tuple[Debt, DebtView]:
        debt = self.debts.get(household_id, debt_id)
        if not debt:
            raise NotFoundError("Debt not found")
        linked = self.transactions.for_debt(household_id, debt_id)
        return debt, portfolio_math.view_debt(debt, linked, today)

    # ---------------------------------------------------------- validation
    def validate_links(
        self,
        household_id: int,
        txn_type: str,
        investment_id: Optional[int],
        debt_id: Optional[int],
    ) -> tuple[Optional[int], Optional[int]]:
        """Check a transaction's portfolio links and return the pair that
        should actually be stored.

        A link only means something for the matching transaction type, so
        changing an EMI into an expense drops its debt link rather than
        leaving a dangling one that would reappear if the type changed
        back. Both are verified to belong to this household — the ids
        arrive from the client, and a foreign key alone wouldn't stop one
        household pointing at another's loan.
        """
        keep_investment: Optional[int] = None
        keep_debt: Optional[int] = None

        if investment_id and txn_type == LINK_TYPE_FOR_INVESTMENT:
            if not self.investments.get(household_id, investment_id):
                raise ValidationError("That investment doesn't exist")
            keep_investment = investment_id
        if debt_id and txn_type == LINK_TYPE_FOR_DEBT:
            if not self.debts.get(household_id, debt_id):
                raise ValidationError("That loan doesn't exist")
            keep_debt = debt_id
        return keep_investment, keep_debt

    def closed_debt_ids(self, household_id: int) -> set[int]:
        """Debts whose derived outstanding has reached zero. The rewards
        engine asks this instead of reading `Debt.outstanding`, which is
        now only the opening balance."""
        return {
            debt.id
            for debt, view in self.debt_views(household_id)
            if view.is_closed and debt.id is not None
        }

    def debt_is_closed(self, household_id: int, debt_id: int) -> bool:
        _, view = self.debt_view(household_id, debt_id)
        return view.is_closed
