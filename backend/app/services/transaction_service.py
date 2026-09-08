"""Transactions. Storage only — the accrual/necessity arithmetic lives in
the frontend's compute.js, keyed off the fields written here."""
from sqlmodel import Session

from app.models import Transaction
from app.models.mixins import now_iso
from app.repositories.repositories import TransactionRepository
from app.schemas.transaction import TransactionIn
from app.services.errors import NotFoundError, ValidationError

_TYPES = {"Expense", "Investment", "Loan", "CC Repayment", "Income"}


class TransactionService:
    def __init__(self, session: Session) -> None:
        self.transactions = TransactionRepository(session)

    def list(self, household_id: int):
        return self.transactions.list(household_id)

    def create(self, household_id: int, data: TransactionIn) -> Transaction:
        self._validate(data)
        return self.transactions.add(
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

    def update(self, household_id: int, txn_id: int, data: TransactionIn) -> Transaction:
        self._validate(data)
        txn = self.transactions.get(household_id, txn_id)
        if not txn:
            raise NotFoundError("Transaction not found")
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
        return self.transactions.save(txn)

    def delete(self, household_id: int, txn_id: int) -> None:
        txn = self.transactions.get(household_id, txn_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        self.transactions.delete(txn)

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
