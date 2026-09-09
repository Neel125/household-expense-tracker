"""Debt DTOs.

`outstanding` is the figure the user typed and stays editable — it is the
balance tracking *started* from. `outstandingNow` is what is left after
the linked EMIs have been amortised against it, and is the number to
show. Keeping both means the edit form has something stable to write back
to while the display always reflects the transactions.
"""
from typing import Optional

from app.schemas.base import CamelModel
from app.services.portfolio_math import DebtView


class DebtIn(CamelModel):
    name: str
    kind: str = "other"
    lender: str = ""
    principal: float = 0
    outstanding: float = 0
    annual_rate_pct: float = 0
    emi: float = 0
    tenure_months: int = 0
    months_paid: int = 0
    start_date: str = ""
    notes: str = ""


class InstalmentOut(CamelModel):
    transaction_id: int
    date: str
    name: str
    paid: float
    interest: float
    principal: float
    balance: float
    accrued_months: float


class DebtOut(CamelModel):
    id: int
    name: str
    kind: str
    lender: str
    principal: float
    outstanding: float  # the opening balance, as entered
    annual_rate_pct: float
    emi: float
    tenure_months: int
    months_paid: int  # EMIs paid before tracking started
    start_date: str
    notes: str
    created_at: str = ""
    updated_at: Optional[str] = None

    # --- derived from linked Loan transactions
    principal_repaid: float = 0
    interest_paid: float = 0
    total_paid: float = 0
    # What is actually left to pay. This is the number the UI shows.
    outstanding_now: float = 0
    emis_paid: float = 0
    is_closed: bool = False
    payoff_pct: float = 0
    payment_count: int = 0
    last_payment_date: str = ""

    @classmethod
    def of(cls, debt, view: DebtView) -> "DebtOut":
        return cls(
            **{
                **{
                    k: getattr(debt, k)
                    for k in (
                        "id",
                        "name",
                        "kind",
                        "lender",
                        "principal",
                        "outstanding",
                        "annual_rate_pct",
                        "emi",
                        "tenure_months",
                        "months_paid",
                        "start_date",
                        "notes",
                        "created_at",
                        "updated_at",
                    )
                },
                "principal_repaid": view.principal_repaid,
                "interest_paid": view.interest_paid,
                "total_paid": view.total_paid,
                "outstanding_now": view.outstanding,
                "emis_paid": view.emis_paid,
                "is_closed": view.is_closed,
                "payoff_pct": view.payoff_pct,
                "payment_count": len(view.instalments),
                "last_payment_date": view.last_payment_date,
            }
        )


class DebtScheduleOut(CamelModel):
    """One loan plus the interest/principal split of every EMI logged
    against it — the answer to "where did my EMI actually go?"."""

    debt: DebtOut
    instalments: list[InstalmentOut]

    @classmethod
    def of(cls, debt, view: DebtView) -> "DebtScheduleOut":
        return cls(
            debt=DebtOut.of(debt, view),
            instalments=[InstalmentOut.model_validate(i) for i in view.instalments],
        )
