from typing import Optional

from sqlmodel import Field, SQLModel

# The two ways a transaction pays a debt. EMI (`Loan`) is amortised into
# interest + principal; a partial payment goes entirely to principal.
TYPE_LOAN = "Loan"
TYPE_LOAN_PARTIAL = "Loan Partial"
LOAN_PAYMENT_TYPES = (TYPE_LOAN, TYPE_LOAN_PARTIAL)


class Transaction(SQLModel, table=True):
    """One financial entry. The credit-card accrual rules that the
    dashboard depends on live in the frontend's compute.js and key off
    `type`, `payment_mode`, `provider_type` and `account` — those are kept
    intact; `category_id`, `merchant` and Income support are additive."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    date: str  # "YYYY-MM-DD"
    name: str
    # Expense | Investment | Loan | Loan Partial | CC Repayment | Income
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
    # holding; a `Loan` or `Loan Partial` row pays a debt. EMIs are split
    # into interest and principal; partials reduce principal in full.
    # Both nullable: a transaction is perfectly valid unlinked, which is
    # what every row created before this feature is.
    investment_id: Optional[int] = Field(default=None, foreign_key="investment.id")
    debt_id: Optional[int] = Field(default=None, foreign_key="debt.id")
    created_at: str = ""
    updated_at: Optional[str] = None
