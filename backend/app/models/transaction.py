from typing import Optional

from sqlmodel import Field, SQLModel


class Transaction(SQLModel, table=True):
    """One financial entry. The credit-card accrual rules that the
    dashboard depends on live in the frontend's compute.js and key off
    `type`, `payment_mode`, `provider_type` and `account` — those are kept
    intact; `category_id`, `merchant` and Income support are additive."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    date: str  # "YYYY-MM-DD"
    name: str
    # Expense | Investment | Loan | CC Repayment | Income
    type: str
    amount: float
    payment_mode: str = ""  # UPI | Credit Card | Cash | Auto Debit | Debit Card | ...
    provider_type: str = ""  # bank or card name (matches an Account name)
    necessity: str = ""  # Need | Want | Investment | Debt (blank for Income)
    account: str = ""  # which card/loan a CC Repayment or Loan settles
    member: str = ""  # who logged it (member name)
    category_id: Optional[int] = Field(default=None, foreign_key="category.id")
    merchant: str = ""  # where it was spent, for merchant analysis
    # Portfolio links. An `Investment` row makes this a contribution to a
    # holding; a `Loan` row makes it an EMI against a debt, and
    # services.portfolio_math splits it into interest and principal.
    # Both nullable: a transaction is perfectly valid unlinked, which is
    # what every row created before this feature is.
    investment_id: Optional[int] = Field(default=None, foreign_key="investment.id")
    debt_id: Optional[int] = Field(default=None, foreign_key="debt.id")
    created_at: str = ""
    updated_at: Optional[str] = None
