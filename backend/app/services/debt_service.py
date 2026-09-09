"""Household debts (home/car/personal/consumer loans and other EMIs).

This service owns a debt's own terms — lender, rate, EMI, tenure. What
is actually still owed is not stored here: `outstanding` is the balance
tracking began from, and the linked `Loan` transactions amortise it (see
services.portfolio_math). So the payoff test asks the portfolio read
model rather than trusting the column.

It publishes a single reward-worthy event: DEBT_COMPLETED, when a loan
that had something left to pay no longer does. The handler translates the
debt's *kind* into the appropriate coin tier (home vs car vs other) —
this layer only reports the fact.
"""
from typing import Optional

from sqlmodel import Session

from app.models import Debt
from app.models.debt import DEBT_KINDS
from app.models.mixins import now_iso
from app.repositories.repositories import DebtRepository
from app.schemas.debt import DebtIn
from app.services import events
from app.services.errors import NotFoundError, ValidationError
from app.services.portfolio_service import PortfolioService


class DebtService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.debts = DebtRepository(session)
        self.portfolio = PortfolioService(session)

    def list(self, household_id: int):
        return self.debts.list(household_id)

    def create(
        self, household_id: int, data: DebtIn, actor_id: Optional[int] = None
    ) -> Debt:
        payload = self._validate(data)
        obj = self.debts.add(
            Debt(
                household_id=household_id,
                created_at=now_iso(),
                **payload,
            )
        )
        # Creating a debt with outstanding=0 is a strange but harmless
        # thing to do (migrating in a paid-off loan for the history).
        # We deliberately do *not* fire DEBT_COMPLETED on create: coins
        # are for closing a loan, not for typing "0" into a form.
        return obj

    def update(
        self,
        household_id: int,
        obj_id: int,
        data: DebtIn,
        actor_id: Optional[int] = None,
    ) -> Debt:
        obj = self.debts.get(household_id, obj_id)
        if not obj:
            raise NotFoundError("Debt not found")
        # Snapshot whether the loan was already closed, so we can tell
        # whether *this* save is the one that closed it. Reading it here
        # (before the setattr loop) avoids depending on session state.
        # `outstanding` alone can't answer that any more — it is only the
        # balance tracking started from, and linked EMIs pay it down.
        _, before = self.portfolio.debt_view(household_id, obj_id)
        was_closed = before.is_closed

        for k, v in self._validate(data).items():
            setattr(obj, k, v)
        obj.updated_at = now_iso()
        obj = self.debts.save(obj)

        _, after = self.portfolio.debt_view(household_id, obj_id)
        if not was_closed and after.is_closed:
            self._announce_completed(obj, actor_id)
        return obj

    def delete(self, household_id: int, obj_id: int) -> None:
        obj = self.debts.get(household_id, obj_id)
        if not obj:
            raise NotFoundError("Debt not found")
        self.debts.delete(obj)

    # ---------------------------------------------------------- publishing
    def _announce_completed(self, obj: Debt, actor_id: Optional[int]) -> None:
        events.publish(
            self.session,
            events.DomainEvent(
                name=events.DEBT_COMPLETED,
                household_id=obj.household_id,
                user_id=actor_id,
                payload={
                    "debt_id": obj.id,
                    "name": obj.name,
                    "kind": obj.kind,
                },
            ),
        )

    # ---------------------------------------------------------- validation
    @staticmethod
    def _validate(data: DebtIn) -> dict:
        name = (data.name or "").strip()
        if not name:
            raise ValidationError("Debt needs a name")
        kind = (data.kind or "other").strip().lower()
        if kind not in DEBT_KINDS:
            raise ValidationError(f"Unknown debt kind: {kind}")

        principal = float(data.principal or 0)
        outstanding = float(data.outstanding or 0)
        emi = float(data.emi or 0)
        rate = float(data.annual_rate_pct or 0)
        tenure = int(data.tenure_months or 0)
        months_paid = int(data.months_paid or 0)

        if principal < 0 or outstanding < 0 or emi < 0 or rate < 0:
            raise ValidationError("Amounts and rate can't be negative")
        if tenure < 0 or months_paid < 0:
            raise ValidationError("Tenure and months paid can't be negative")
        if tenure and months_paid > tenure:
            raise ValidationError("Months paid can't exceed the original tenure")

        return {
            "name": name,
            "kind": kind,
            "lender": (data.lender or "").strip(),
            "principal": principal,
            "outstanding": outstanding,
            "annual_rate_pct": rate,
            "emi": emi,
            "tenure_months": tenure,
            "months_paid": months_paid,
            "start_date": (data.start_date or "").strip(),
            "notes": (data.notes or "").strip(),
        }
