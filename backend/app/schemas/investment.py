"""Investment DTOs.

`amountInvested` is what the user typed and remains editable — it is the
*opening* figure, i.e. money that went in before any transaction was
linked. Everything derived from linked contributions arrives alongside it
(`contributed`, `totalInvested`, `projectedValue`), so a contribution
that was also baked into the opening figure shows up as an overlap the
user can see and fix, rather than being silently double-counted.
"""
from typing import Optional

from app.schemas.base import CamelModel
from app.services.portfolio_math import InvestmentView


class InvestmentIn(CamelModel):
    name: str
    kind: str = "other"
    institution: str = ""
    amount_invested: float = 0
    current_value: float = 0
    annual_return_pct: float = 0
    monthly_contribution: float = 0
    start_date: str = ""
    maturity_date: str = ""
    notes: str = ""


class InvestmentWithdrawIn(CamelModel):
    """Close a holding and credit the proceeds to a bank/cash account."""

    date: str = ""
    # None = use the holding's current effective value.
    amount: Optional[float] = None
    account_name: str
    member: str = ""
    payment_mode: str = "Net Banking"


class InvestmentReinvestIn(CamelModel):
    """Close a holding and open a successor. The matured proceeds become
    the new opening invested; only `addOnAmount` is logged as a
    transaction from the bank."""

    date: str = ""
    # Matured proceeds. None = the holding's current effective value.
    amount: Optional[float] = None
    add_on_amount: float = 0
    account_name: str = ""
    new_name: str = ""
    new_maturity_date: str = ""
    annual_return_pct: Optional[float] = None
    member: str = ""
    notes: str = ""
    payment_mode: str = "Net Banking"


class ContributionOut(CamelModel):
    transaction_id: int
    date: str
    name: str
    amount: float
    grown_to: float


class LedgerEntryOut(CamelModel):
    """One auto-logged (or linked) row on a holding: money in, money out,
    or an add-on at renewal."""

    transaction_id: int
    date: str
    name: str
    amount: float
    kind: str  # contribution | withdrawal
    provider_type: str = ""


class InvestmentOut(CamelModel):
    id: int
    name: str
    kind: str
    institution: str
    amount_invested: float  # the opening figure, as entered
    current_value: float  # the user's own valuation; 0 = not set
    annual_return_pct: float
    monthly_contribution: float
    start_date: str
    maturity_date: str
    notes: str
    created_at: str = ""
    updated_at: Optional[str] = None
    is_closed: bool = False
    closed_at: str = ""
    closed_to_account: str = ""
    successor_id: Optional[int] = None
    # What the holding was worth at close. Zero while it is still open.
    closed_value: float = 0

    # --- derived from linked Investment transactions
    contributed: float = 0
    total_invested: float = 0
    projected_value: float = 0
    # What the UI should show as today's worth: the manual valuation when
    # there is one, else the projection.
    effective_value: float = 0
    value_is_manual: bool = False
    gain: float = 0
    gain_pct: float = 0
    contribution_count: int = 0
    last_contribution_date: str = ""

    @classmethod
    def of(cls, investment, view: InvestmentView) -> "InvestmentOut":
        return cls(
            **{
                **{
                    k: getattr(investment, k)
                    for k in (
                        "id",
                        "name",
                        "kind",
                        "institution",
                        "amount_invested",
                        "current_value",
                        "annual_return_pct",
                        "monthly_contribution",
                        "start_date",
                        "maturity_date",
                        "notes",
                        "created_at",
                        "updated_at",
                    )
                },
                "is_closed": bool(getattr(investment, "closed", False)),
                "closed_at": getattr(investment, "closed_at", "") or "",
                "closed_to_account": getattr(investment, "closed_to_account", "") or "",
                "successor_id": getattr(investment, "successor_id", None),
                "closed_value": view.closed_value,
                "contributed": view.contributed,
                "total_invested": view.total_invested,
                "projected_value": view.projected_value,
                "effective_value": view.effective_value,
                "value_is_manual": view.value_is_manual,
                "gain": view.gain,
                "gain_pct": view.gain_pct,
                "contribution_count": view.contribution_count,
                "last_contribution_date": view.last_contribution_date,
            }
        )


class InvestmentDetailOut(CamelModel):
    """One holding plus every contribution that built it, and the full
    in/out ledger (withdrawals and add-ons included)."""

    investment: InvestmentOut
    contributions: list[ContributionOut]
    ledger: list[LedgerEntryOut] = []

    @classmethod
    def of(
        cls,
        investment,
        view: InvestmentView,
        ledger: Optional[list[LedgerEntryOut]] = None,
    ) -> "InvestmentDetailOut":
        return cls(
            investment=InvestmentOut.of(investment, view),
            contributions=[ContributionOut.model_validate(c) for c in view.contributions],
            ledger=ledger or [],
        )


class InvestmentReinvestOut(CamelModel):
    """The closed original holding and the successor it rolled into."""

    closed: InvestmentOut
    created: InvestmentOut
