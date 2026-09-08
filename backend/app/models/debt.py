from typing import Optional

from sqlmodel import Field, SQLModel

# Structured loans / EMIs. This is distinct from an Account of type
# "loan" (which is a lightweight ledger entry) — a Debt captures the
# terms of a formal loan so the app can show remaining tenure, next EMI
# date and the total interest still to pay.
DEBT_KINDS = {
    "home_loan",
    "car_loan",
    "personal_loan",
    "consumer_loan",   # phones, electronics, appliances on EMI
    "education_loan",
    "business_loan",
    "credit_card_debt",
    "other",
}


class Debt(SQLModel, table=True):
    """An outstanding household liability with an EMI schedule."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str
    kind: str = "other"
    lender: str = ""              # e.g. "SBI Bank", "Bajaj Finserv"
    principal: float = 0          # original loan amount
    outstanding: float = 0        # current outstanding balance
    annual_rate_pct: float = 0
    emi: float = 0
    tenure_months: int = 0        # original tenure in months
    months_paid: int = 0          # how many EMIs already paid
    start_date: str = ""          # YYYY-MM-DD
    notes: str = ""
    created_at: str = ""
    updated_at: Optional[str] = None
