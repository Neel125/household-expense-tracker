from typing import Optional

from sqlmodel import Field, SQLModel

# Account kinds. Credit cards keep the existing accrual/repayment
# reconciliation; banks/cash/debit hold a running balance.
ACCOUNT_TYPES = {"bank", "debit_card", "credit_card", "cash", "loan"}


class Account(SQLModel, table=True):
    """A place money sits or is owed: a bank, its debit card, a credit
    card, cash, or a loan. Replaces the old free-text card/loan lists."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str
    type: str = "bank"
    institution: str = ""  # e.g. "HDFC Bank"
    opening_balance: float = 0
    # A debit card belongs to a bank account; null for standalone accounts.
    linked_account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    archived: bool = False
    created_at: str = ""
    updated_at: Optional[str] = None
