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

_TYPES = {"Expense", "Investment", "Loan", "CC Repayment", "Income"}
# Only day-to-day spending is "tracking an expense". A CC repayment or an
# income line is bookkeeping the app largely derives, so neither earns the
# logging coin.
_TRACKABLE = "Expense"


class TransactionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.transactions = TransactionRepository(session)

    def list(self, household_id: int):
        return self.transactions.list(household_id)

    def create(
        self, household_id: int, data: TransactionIn, actor_id: Optional[int] = None
    ) -> Transaction:
        self._validate(data)
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
                created_at=now_iso(),
            )
        )
        if txn.type == _TRACKABLE:
            self._publish(events.EXPENSE_TRACKED, txn, actor_id)
        return txn

    def update(
        self, household_id: int, txn_id: int, data: TransactionIn, actor_id: Optional[int] = None
    ) -> Transaction:
        self._validate(data)
        txn = self.transactions.get(household_id, txn_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        was_trackable = txn.type == _TRACKABLE
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
        return saved

    def delete(self, household_id: int, txn_id: int, actor_id: Optional[int] = None) -> None:
        txn = self.transactions.get(household_id, txn_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        was_trackable = txn.type == _TRACKABLE
        snapshot = events.DomainEvent(
            name=events.EXPENSE_DELETED,
            household_id=household_id,
            user_id=actor_id,
            payload={"transaction_id": txn.id, "amount": txn.amount, "name": txn.name},
        )
        self.transactions.delete(txn)
        if was_trackable:
            events.publish(self.session, snapshot)

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
