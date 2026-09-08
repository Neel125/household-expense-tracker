"""Bank / debit card / credit card / cash / loan accounts."""
from sqlmodel import Session

from app.models import Account
from app.models.account import ACCOUNT_TYPES
from app.models.mixins import now_iso
from app.repositories.repositories import AccountRepository
from app.schemas.account import AccountIn
from app.services.errors import NotFoundError, ValidationError


class AccountService:
    def __init__(self, session: Session) -> None:
        self.accounts = AccountRepository(session)

    def list(self, household_id: int):
        return self.accounts.list(household_id)

    def create(self, household_id: int, data: AccountIn) -> Account:
        self._validate(data)
        return self.accounts.add(
            Account(
                household_id=household_id,
                name=data.name.strip(),
                type=data.type,
                institution=data.institution.strip(),
                opening_balance=float(data.opening_balance or 0),
                linked_account_id=data.linked_account_id,
                archived=bool(data.archived),
                created_at=now_iso(),
            )
        )

    def update(self, household_id: int, account_id: int, data: AccountIn) -> Account:
        self._validate(data)
        account = self.accounts.get(household_id, account_id)
        if not account:
            raise NotFoundError("Account not found")
        account.name = data.name.strip()
        account.type = data.type
        account.institution = data.institution.strip()
        account.opening_balance = float(data.opening_balance or 0)
        account.linked_account_id = data.linked_account_id
        account.archived = bool(data.archived)
        account.updated_at = now_iso()
        return self.accounts.save(account)

    def delete(self, household_id: int, account_id: int) -> None:
        account = self.accounts.get(household_id, account_id)
        if not account:
            raise NotFoundError("Account not found")
        self.accounts.delete(account)

    @staticmethod
    def _validate(data: AccountIn) -> None:
        if not data.name.strip():
            raise ValidationError("An account needs a name")
        if data.type not in ACCOUNT_TYPES:
            raise ValidationError(f"Unknown account type '{data.type}'")
