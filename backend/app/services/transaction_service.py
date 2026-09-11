"""Transactions. Storage only — the accrual/necessity arithmetic lives in
the frontend's compute.js, keyed off the fields written here.

Writes announce themselves on the domain event bus. This service has no
idea that a coin is awarded when an expense is logged; it states the fact
and the rewards engine decides what it is worth (see services.events).
"""
from typing import Optional

from sqlmodel import Session

from app.models import Transaction
from app.models.mixins import now_iso
from app.repositories.repositories import TransactionRepository
from app.schemas.transaction import TransactionIn
from app.services import events
from app.services.errors import NotFoundError, ValidationError
from app.services.portfolio_service import PortfolioService

_TYPES = {"Expense", "Investment", "Loan", "Loan Partial", "CC Repayment", "Income"}
# Only day-to-day spending is "tracking an expense". A CC repayment or an
# income line is bookkeeping the app largely derives, so neither earns the
# logging coin.
_TRACKABLE = "Expense"


class TransactionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.transactions = TransactionRepository(session)
        # Portfolio links are validated here and read back through the
        # same service, so an EMI and the loan it pays down can never
        # disagree about which household they belong to.
        self.portfolio = PortfolioService(session)

    def list(self, household_id: int):
        return self.transactions.list(household_id)

    def create(
        self, household_id: int, data: TransactionIn, actor_id: Optional[int] = None
    ) -> Transaction:
        self._validate(data)
        investment_id, debt_id = self.portfolio.validate_links(
            household_id, data.type, data.investment_id, data.debt_id
        )
        txn = self.transactions.add(
            Transaction(
                household_id=household_id,
                date=data.date,
                name=data.name.strip(),
                type=data.type,
                amount=float(data.amount or 0),
                payment_mode=data.payment_mode,
                provider_type=data.provider_type,
                necessity=data.necessity,
                account=data.account,
                member=data.member,
                category_id=data.category_id,
                merchant=data.merchant.strip(),
                investment_id=investment_id,
                debt_id=debt_id,
                created_at=now_iso(),
            )
        )
        if txn.type == _TRACKABLE:
            self._publish(events.EXPENSE_TRACKED, txn, actor_id)
        self._settle_linked_debt(household_id, debt_id, actor_id)
        return txn

    def update(
        self, household_id: int, txn_id: int, data: TransactionIn, actor_id: Optional[int] = None
    ) -> Transaction:
        self._validate(data)
        txn = self.transactions.get(household_id, txn_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        was_trackable = txn.type == _TRACKABLE
        previous_debt_id = txn.debt_id
        investment_id, debt_id = self.portfolio.validate_links(
            household_id, data.type, data.investment_id, data.debt_id
        )
        txn.date = data.date
        txn.name = data.name.strip()
        txn.type = data.type
        txn.amount = float(data.amount or 0)
        txn.payment_mode = data.payment_mode
        txn.provider_type = data.provider_type
        txn.necessity = data.necessity
        txn.account = data.account
        txn.member = data.member
        txn.category_id = data.category_id
        txn.merchant = data.merchant.strip()
        txn.investment_id = investment_id
        txn.debt_id = debt_id
        txn.updated_at = now_iso()
        saved = self.transactions.save(txn)

        # Editing an expense into something else (or back) has to move the
        # coin with it, or the ledger would claim a reward for a row that
        # is no longer an expense. Re-awarding is blocked by the ledger's
        # idempotency key, so flipping a row back and forth cannot mint
        # coins — it just doesn't refund the reversed one.
        is_trackable = saved.type == _TRACKABLE
        if was_trackable and not is_trackable:
            self._publish(events.EXPENSE_DELETED, saved, actor_id)
        elif is_trackable and not was_trackable:
            self._publish(events.EXPENSE_TRACKED, saved, actor_id)

        # Moving or re-amounting an EMI can close a loan — or reopen the
        # one it used to pay, so both ends are re-checked. Nothing needs
        # undoing when a loan reopens: the reward ledger keys the payoff
        # by debt id, and a reopened loan simply isn't paid again.
        for candidate in {debt_id, previous_debt_id}:
            self._settle_linked_debt(household_id, candidate, actor_id)
        return saved

    def delete(self, household_id: int, txn_id: int, actor_id: Optional[int] = None) -> None:
        txn = self.transactions.get(household_id, txn_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        was_trackable = txn.type == _TRACKABLE
        linked_debt_id = txn.debt_id
        snapshot = events.DomainEvent(
            name=events.EXPENSE_DELETED,
            household_id=household_id,
            user_id=actor_id,
            payload={"transaction_id": txn.id, "amount": txn.amount, "name": txn.name},
        )
        self.transactions.delete(txn)
        if was_trackable:
            events.publish(self.session, snapshot)
        self._settle_linked_debt(household_id, linked_debt_id, actor_id)

    def _settle_linked_debt(
        self, household_id: int, debt_id: Optional[int], actor_id: Optional[int]
    ) -> None:
        """Announce a loan that this write has paid off.

        The outstanding balance is derived from the linked EMIs, so the
        only way to notice a payoff is to re-derive it after the write.
        DEBT_COMPLETED is idempotent on the reward side, so publishing it
        again for an already-closed loan costs nothing.
        """
        if not debt_id:
            return
        debt, view = self.portfolio.debt_view(household_id, debt_id)
        if not view.is_closed:
            return
        events.publish(
            self.session,
            events.DomainEvent(
                name=events.DEBT_COMPLETED,
                household_id=household_id,
                user_id=actor_id,
                payload={"debt_id": debt.id, "name": debt.name, "kind": debt.kind},
            ),
        )

    def _publish(self, name: str, txn: Transaction, actor_id: Optional[int]) -> None:
        events.publish(
            self.session,
            events.DomainEvent(
                name=name,
                household_id=txn.household_id,
                user_id=actor_id,
                payload={"transaction_id": txn.id, "amount": txn.amount, "name": txn.name},
            ),
        )

    @staticmethod
    def _validate(data: TransactionIn) -> None:
        if not data.date:
            raise ValidationError("A transaction needs a date")
        if not data.name.strip():
            raise ValidationError("A transaction needs a name")
        if data.type not in _TYPES:
            raise ValidationError(f"Unknown transaction type '{data.type}'")
        if not data.amount:
            raise ValidationError("A transaction needs an amount")
