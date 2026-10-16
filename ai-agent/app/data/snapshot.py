"""One household's books, loaded once per request.

Every tool the agent can call reads this object rather than the database.
Three reasons, all of which matter more than the memory it costs:

- **Consistency.** An agent run makes many tool calls over many seconds.
  Reading live each time lets the books change underneath a single
  analysis, so the forecast could disagree with the budget it was
  derived from. A snapshot makes one run see one set of facts.
- **Cost.** The number of database round trips is a function of the
  number of *requests*, not of how many times the model decides to look
  at something.
- **Tenancy.** The `household_id` filter is applied exactly once, here.
  Tools are built as closures over a loaded snapshot (see
  app/agent/tools.py), so a tool has no way to name another household —
  it never sees an id to pass.

A household's ledger is small (a family logs thousands of rows, not
millions), so loading it whole is the cheap option.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from sqlmodel import Session, select

from app.data.models import (
    Account,
    Category,
    CategoryBudget,
    Debt,
    Goal,
    Household,
    IncomeSource,
    Investment,
    Member,
    Transaction,
    Vehicle,
    VehicleRecord,
)


class HouseholdNotFound(Exception):
    """Raised when the backend asks about a household that isn't there."""


@dataclass(frozen=True)
class HouseholdSnapshot:
    """Everything the analysis layer is allowed to know."""

    household: Household
    as_of: date
    transactions: list[Transaction]
    categories: list[Category]
    category_budgets: list[CategoryBudget]
    income_sources: list[IncomeSource]
    accounts: list[Account]
    goals: list[Goal]
    investments: list[Investment]
    debts: list[Debt]
    members: list[Member]
    vehicles: list[Vehicle]
    vehicle_records: list[VehicleRecord]

    # --- indices, built once in __post_init__
    _category_by_id: dict[int, Category] = field(default_factory=dict, repr=False)
    _category_by_name: dict[str, Category] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for c in self.categories:
            if c.id is not None:
                self._category_by_id[c.id] = c
            self._category_by_name[c.name.casefold()] = c

    # ------------------------------------------------------------ lookups
    def category_name(self, category_id: Optional[int]) -> str:
        if category_id is None:
            return "Uncategorised"
        found = self._category_by_id.get(category_id)
        return found.name if found else "Uncategorised"

    def category_id_for(self, name: str) -> Optional[int]:
        found = self._category_by_name.get((name or "").casefold())
        return found.id if found else None

    @property
    def active_categories(self) -> list[Category]:
        return [c for c in self.categories if not c.archived]

    @property
    def monthly_budget(self) -> float:
        return float(self.household.monthly_budget or 0)

    @property
    def recurring_monthly_income(self) -> float:
        return sum(float(s.monthly_amount or 0) for s in self.income_sources if s.active)

    @property
    def expenses(self) -> list[Transaction]:
        """Rows that represent consumption. The credit-card rule the whole
        app runs on: a card purchase counts on the day it is made, and the
        later repayment is cash movement, not a second expense."""
        from app.data.models import CONSUMPTION_TYPES

        return [t for t in self.transactions if t.type in CONSUMPTION_TYPES]

    @property
    def credit_cards(self) -> list[Account]:
        return [a for a in self.accounts if a.type == "credit_card" and not a.archived]

    def has_any_data(self) -> bool:
        return bool(self.transactions or self.investments or self.debts or self.goals)


def _rows(session: Session, model, household_id: int) -> list:
    return list(session.exec(select(model).where(model.household_id == household_id)).all())


def load_snapshot(
    session: Session,
    household_id: int,
    as_of: Optional[date] = None,
) -> HouseholdSnapshot:
    """Read one household's whole ledger. The only place `household_id`
    is applied — see the module docstring."""
    household = session.get(Household, household_id)
    if household is None:
        raise HouseholdNotFound(f"Household {household_id} does not exist")

    transactions = _rows(session, Transaction, household_id)
    # Chronological, with the row id as a stable tie-break, so every
    # downstream calculation (amortisation especially) sees one order.
    transactions.sort(key=lambda t: ((t.date or ""), t.id or 0))

    return HouseholdSnapshot(
        household=household,
        as_of=as_of or date.today(),
        transactions=transactions,
        categories=_rows(session, Category, household_id),
        category_budgets=_rows(session, CategoryBudget, household_id),
        income_sources=_rows(session, IncomeSource, household_id),
        accounts=_rows(session, Account, household_id),
        goals=_rows(session, Goal, household_id),
        investments=_rows(session, Investment, household_id),
        debts=_rows(session, Debt, household_id),
        members=_rows(session, Member, household_id),
        vehicles=_rows(session, Vehicle, household_id),
        vehicle_records=_rows(session, VehicleRecord, household_id),
    )


def transactions_for_investment(
    snapshot: HouseholdSnapshot, investment_id: int
) -> Sequence[Transaction]:
    """Contributions to one holding. The type filter matters: a row
    re-typed away from Investment stops counting even if the link is
    still on it (same rule as the backend's repository)."""
    from app.data.models import TYPE_INVESTMENT

    return [
        t
        for t in snapshot.transactions
        if t.investment_id == investment_id and t.type == TYPE_INVESTMENT
    ]


def transactions_for_debt(snapshot: HouseholdSnapshot, debt_id: int) -> Sequence[Transaction]:
    from app.data.models import LOAN_PAYMENT_TYPES

    return [
        t for t in snapshot.transactions if t.debt_id == debt_id and t.type in LOAN_PAYMENT_TYPES
    ]
