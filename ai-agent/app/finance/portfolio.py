"""Capability 5 — analyse investments, and the debt half of capability 6.

The amortisation and contribution-growth maths is a port of
`backend/app/services/portfolio_math.py`. It is duplicated rather than
imported because the agent runs in its own container, and the figures it
quotes have to be the same figures the Portfolio page shows — an agent
that disagrees with the app about how much a loan still owes is worse
than no agent. **If that file changes, this one changes with it.**

On top of the ported maths, this module adds what an analyst would
actually say about a portfolio and never about a single holding:

- allocation by asset kind, and whether any one holding or kind is a
  concentration risk;
- an annualised return per holding, so a 12% gain over four years is not
  mistaken for a good year;
- which SIPs and RDs have gone quiet;
- which deposits mature soon and therefore need a decision;
- the debt side: outstanding, interest still to run, and which loan is
  worth prepaying first.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from app.data.models import (
    MATURING_INVESTMENT_KINDS,
    RECURRING_INVESTMENT_KINDS,
    TYPE_LOAN,
    TYPE_LOAN_PARTIAL,
    Debt,
    Investment,
    Transaction,
)
from app.data.snapshot import (
    HouseholdSnapshot,
    transactions_for_debt,
    transactions_for_investment,
)
from app.finance.month import parse_date

# Average days in a month over a 400-year cycle — turns a gap between two
# dates into "months of interest".
DAYS_PER_MONTH = 30.4375
# A gap longer than this is almost certainly a back-dated entry rather
# than a year of unpaid interest, so accrual is capped instead of
# producing a shock number.
MAX_ACCRUAL_MONTHS = 12.0

# A single holding above this share of the portfolio is flagged.
CONCENTRATION_PCT = 40.0
# An SIP or RD with no contribution for this long has probably stopped.
SIP_STALE_DAYS = 45


def _months_between(start: Optional[date], end: Optional[date]) -> float:
    if not start or not end or end <= start:
        return 0.0
    return (end - start).days / DAYS_PER_MONTH


def _grow(amount: float, annual_rate_pct: float, months: float) -> float:
    """Compound monthly. A zero rate is the identity — an unrated holding
    gets no invented growth."""
    if amount <= 0 or annual_rate_pct <= 0 or months <= 0:
        return max(0.0, amount)
    return amount * (1 + annual_rate_pct / 100 / 12) ** months


def _by_date(txns: Sequence[Transaction]) -> list[Transaction]:
    return sorted(txns, key=lambda t: ((t.date or ""), t.id or 0))


# ---------------------------------------------------------------- holdings
@dataclass(frozen=True)
class HoldingView:
    id: int
    name: str
    kind: str
    institution: str
    opening_invested: float
    contributed: float
    total_invested: float
    projected_value: float
    effective_value: float
    value_is_manual: bool
    gain: float
    gain_pct: float
    annualised_pct: Optional[float]
    years_held: float
    monthly_contribution: float
    contribution_count: int
    last_contribution_date: str
    maturity_date: str
    days_to_maturity: Optional[int]
    is_stale_sip: bool
    is_closed: bool = False
    closed_value: float = 0

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "institution": self.institution,
            "totalInvested": round(self.total_invested, 2),
            "currentValue": round(self.effective_value, 2),
            "valueIsManual": self.value_is_manual,
            "projectedValue": round(self.projected_value, 2),
            "gain": round(self.gain, 2),
            "gainPct": round(self.gain_pct, 2),
            "annualisedPct": self.annualised_pct,
            "yearsHeld": round(self.years_held, 2),
            "monthlyContribution": round(self.monthly_contribution, 2),
            "contributionCount": self.contribution_count,
            "lastContributionDate": self.last_contribution_date,
            "maturityDate": self.maturity_date,
            "daysToMaturity": self.days_to_maturity,
            "isStaleSip": self.is_stale_sip,
            "isClosed": self.is_closed,
            "closedValue": round(self.closed_value, 2),
        }


def view_holding(
    investment: Investment, linked: Sequence[Transaction], today: date
) -> HoldingView:
    rate = float(investment.annual_return_pct or 0)

    # `amount_invested` is what the user maintained by hand before any
    # transaction was linked, so it is the opening balance and linked
    # contributions stack on top of it.
    opening = max(0.0, float(investment.amount_invested or 0))
    opening_from = parse_date(investment.start_date) or parse_date(investment.created_at)
    projected = _grow(opening, rate, _months_between(opening_from, today))

    contributed = 0.0
    ordered = _by_date(linked)
    for txn in ordered:
        amount = max(0.0, float(txn.amount or 0))
        contributed += amount
        projected += _grow(amount, rate, _months_between(parse_date(txn.date), today))

    total_invested = opening + contributed
    manual = float(investment.current_value or 0)
    value_is_manual = manual > 0
    live_value = manual if value_is_manual else projected
    closed = bool(getattr(investment, "closed", False))
    effective = 0.0 if closed else live_value
    closed_value = live_value if closed else 0.0
    gain_from = closed_value if closed else effective
    gain = gain_from - total_invested

    # Annualised from the holding's own start, which is the only figure
    # that lets two holdings of different ages be compared.
    start = opening_from or (parse_date(ordered[0].date) if ordered else None)
    years = max(0.0, (today - start).days / 365.25) if start else 0.0
    annualised: Optional[float] = None
    # Under a year, annualising magnifies noise into a headline, so it is
    # withheld rather than overstated.
    if years >= 1.0 and total_invested > 0 and effective > 0:
        annualised = round(((effective / total_invested) ** (1 / years) - 1) * 100, 2)

    last_contribution = ordered[-1].date if ordered else ""
    maturity = parse_date(investment.maturity_date)
    last_date = parse_date(last_contribution)
    stale = bool(
        not closed
        and investment.kind in RECURRING_INVESTMENT_KINDS
        and float(investment.monthly_contribution or 0) > 0
        and (last_date is None or (today - last_date).days > SIP_STALE_DAYS)
    )

    return HoldingView(
        id=investment.id or 0,
        name=investment.name,
        kind=investment.kind,
        institution=investment.institution,
        opening_invested=opening,
        contributed=contributed,
        total_invested=total_invested,
        projected_value=projected,
        effective_value=effective,
        value_is_manual=value_is_manual and not closed,
        gain=gain,
        gain_pct=round(gain / total_invested * 100, 2) if total_invested > 0 else 0.0,
        annualised_pct=annualised,
        years_held=years,
        monthly_contribution=0.0 if closed else float(investment.monthly_contribution or 0),
        contribution_count=len(ordered),
        last_contribution_date=last_contribution,
        maturity_date=investment.maturity_date,
        days_to_maturity=None if closed else ((maturity - today).days if maturity else None),
        is_stale_sip=stale,
        is_closed=closed,
        closed_value=closed_value,
    )


# ------------------------------------------------------------------ debts
@dataclass(frozen=True)
class DebtView:
    id: int
    name: str
    kind: str
    lender: str
    opening_outstanding: float
    principal_repaid: float
    interest_paid: float
    outstanding: float
    emi: float
    annual_rate_pct: float
    emis_paid: float
    months_remaining: Optional[int]
    interest_still_to_pay: Optional[float]
    payoff_pct: float
    is_closed: bool
    last_payment_date: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "lender": self.lender,
            "outstanding": round(self.outstanding, 2),
            "principalRepaid": round(self.principal_repaid, 2),
            "interestPaid": round(self.interest_paid, 2),
            "emi": round(self.emi, 2),
            "annualRatePct": round(self.annual_rate_pct, 2),
            "emisPaid": self.emis_paid,
            "monthsRemaining": self.months_remaining,
            "interestStillToPay": (
                round(self.interest_still_to_pay, 2)
                if self.interest_still_to_pay is not None
                else None
            ),
            "payoffPct": round(self.payoff_pct, 2),
            "isClosed": self.is_closed,
            "lastPaymentDate": self.last_payment_date,
        }


def _remaining_tenure(outstanding: float, emi: float, annual_rate_pct: float) -> Optional[int]:
    """Months left at the current EMI, by reducing-balance simulation.

    Returns None when the EMI does not cover the monthly interest — such
    a loan never amortises, and reporting a number there would be a lie
    dressed as arithmetic.
    """
    if outstanding <= 0:
        return 0
    if emi <= 0:
        return None
    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate <= 0:
        import math

        return math.ceil(outstanding / emi)
    if emi <= outstanding * monthly_rate:
        return None
    balance = outstanding
    months = 0
    # 600 months caps a pathological loop; anything beyond 50 years is
    # data entry, not a mortgage.
    while balance > 0 and months < 600:
        balance = balance * (1 + monthly_rate) - emi
        months += 1
    return months


def view_debt(debt: Debt, linked: Sequence[Transaction], today: date) -> DebtView:
    rate = float(debt.annual_rate_pct or 0)
    balance = max(0.0, float(debt.outstanding or 0))
    opening = balance

    principal_repaid = 0.0
    interest_paid = 0.0
    previous: Optional[date] = None
    last_payment = ""

    for txn in _by_date(linked):
        paid = max(0.0, float(txn.amount or 0))
        when = parse_date(txn.date)
        if (txn.type or "") == TYPE_LOAN_PARTIAL:
            # A prepayment reduces principal in full; the interest since
            # the last EMI is left for the next EMI to pick up on the new,
            # lower balance.
            interest = 0.0
            principal = min(paid, balance)
        else:
            # The first linked EMI is assumed to be one ordinary period's
            # interest: the opening balance is "as of now", not as of the
            # loan's start, so accruing from start_date would invent years
            # of interest that has already been paid.
            months = 1.0 if previous is None else min(
                MAX_ACCRUAL_MONTHS, _months_between(previous, when)
            )
            interest = balance * (rate / 100 / 12) * months if rate > 0 and balance > 0 else 0.0
            interest = min(interest, paid)
            # A payment smaller than the interest due pays no principal.
            # Real loans grow in that case; the balance is held flat
            # instead of reporting a debt that rises when you pay it.
            principal = min(max(0.0, paid - interest), balance)
        balance -= principal
        principal_repaid += principal
        interest_paid += interest
        previous = when or previous
        last_payment = txn.date or last_payment

    emi = float(debt.emi or 0)
    emi_count = sum(1 for t in linked if (t.type or "") == TYPE_LOAN)
    total_borrowed = float(debt.principal or 0)
    existed = total_borrowed > 0 or opening > 0
    denominator = total_borrowed if total_borrowed > 0 else opening

    months_remaining = _remaining_tenure(balance, emi, rate)
    interest_ahead = (
        max(0.0, emi * months_remaining - balance)
        if months_remaining not in (None, 0) and emi > 0
        else (0.0 if balance <= 0 else None)
    )

    return DebtView(
        id=debt.id or 0,
        name=debt.name,
        kind=debt.kind,
        lender=debt.lender,
        opening_outstanding=opening,
        principal_repaid=principal_repaid,
        interest_paid=interest_paid,
        outstanding=balance,
        emi=emi,
        annual_rate_pct=rate,
        emis_paid=float(debt.months_paid or 0) + emi_count,
        months_remaining=months_remaining,
        interest_still_to_pay=interest_ahead,
        payoff_pct=(
            round(max(0.0, min(100.0, (denominator - balance) / denominator * 100)), 2)
            if denominator > 0
            else 0.0
        ),
        is_closed=balance <= 0.005 and existed,
        last_payment_date=last_payment,
    )


# ------------------------------------------------------------- the picture
@dataclass(frozen=True)
class PortfolioAnalysis:
    total_invested: float
    current_value: float
    gain: float
    gain_pct: float
    monthly_commitment: float
    holdings: list[HoldingView]
    allocation: list[dict]
    concentrations: list[dict]
    stale_sips: list[dict]
    maturing_soon: list[dict]
    total_debt: float
    total_emi: float
    debts: list[DebtView]
    net_worth: float
    observations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "totalInvested": round(self.total_invested, 2),
            "currentValue": round(self.current_value, 2),
            "gain": round(self.gain, 2),
            "gainPct": round(self.gain_pct, 2),
            "monthlyCommitment": round(self.monthly_commitment, 2),
            "totalDebt": round(self.total_debt, 2),
            "totalEmi": round(self.total_emi, 2),
            "netWorth": round(self.net_worth, 2),
            "allocation": self.allocation,
            "concentrations": self.concentrations,
            "staleSips": self.stale_sips,
            "maturingSoon": self.maturing_soon,
            "holdings": [h.as_dict() for h in self.holdings],
            "debts": [d.as_dict() for d in self.debts],
            "observations": self.observations,
        }


def analyse(snapshot: HouseholdSnapshot, maturity_horizon_days: int = 90) -> PortfolioAnalysis:
    today = snapshot.as_of

    holdings = [
        view_holding(h, transactions_for_investment(snapshot, h.id or 0), today)
        for h in snapshot.investments
    ]
    debts = [
        view_debt(d, transactions_for_debt(snapshot, d.id or 0), today) for d in snapshot.debts
    ]
    open_holdings = [h for h in holdings if not h.is_closed]

    total_invested = sum(h.total_invested for h in open_holdings)
    current_value = sum(h.effective_value for h in open_holdings)
    gain = current_value - total_invested

    by_kind: dict[str, float] = {}
    for holding in open_holdings:
        by_kind[holding.kind] = by_kind.get(holding.kind, 0.0) + holding.effective_value
    allocation = sorted(
        (
            {
                "kind": kind,
                "value": round(value, 2),
                "sharePct": round(value / current_value * 100, 1) if current_value > 0 else 0.0,
            }
            for kind, value in by_kind.items()
        ),
        key=lambda row: -row["value"],
    )

    concentrations = [
        {
            "name": h.name,
            "kind": h.kind,
            "value": round(h.effective_value, 2),
            "sharePct": round(h.effective_value / current_value * 100, 1),
        }
        for h in open_holdings
        if current_value > 0 and h.effective_value / current_value * 100 >= CONCENTRATION_PCT
    ]

    stale_sips = [
        {
            "name": h.name,
            "kind": h.kind,
            "monthlyContribution": round(h.monthly_contribution, 2),
            "lastContributionDate": h.last_contribution_date,
        }
        for h in open_holdings
        if h.is_stale_sip
    ]

    maturing_soon = sorted(
        (
            {
                "name": h.name,
                "kind": h.kind,
                "maturityDate": h.maturity_date,
                "daysToMaturity": h.days_to_maturity,
                "value": round(h.effective_value, 2),
            }
            for h in open_holdings
            if h.days_to_maturity is not None
            and 0 <= h.days_to_maturity <= maturity_horizon_days
            and h.kind in MATURING_INVESTMENT_KINDS
        ),
        key=lambda row: row["daysToMaturity"],
    )

    open_debts = [d for d in debts if not d.is_closed]
    total_debt = sum(d.outstanding for d in open_debts)
    total_emi = sum(d.emi for d in open_debts)

    observations: list[str] = []
    if concentrations:
        top = concentrations[0]
        observations.append(
            f"{top['name']} is {top['sharePct']}% of the portfolio — a single holding "
            f"above {CONCENTRATION_PCT:.0f}% carries more single-name risk than most "
            f"households intend."
        )
    if stale_sips:
        observations.append(
            f"{len(stale_sips)} recurring investment(s) have had no contribution logged "
            f"in over {SIP_STALE_DAYS} days."
        )
    for debt in open_debts:
        # A loan costing more than the portfolio earns is the one
        # arbitrage a household can always make.
        if debt.annual_rate_pct >= 12 and debt.outstanding > 0:
            observations.append(
                f"{debt.name} runs at {debt.annual_rate_pct:.1f}% with "
                f"₹{debt.outstanding:,.0f} outstanding — a guaranteed return that most "
                f"investments cannot match."
            )
    if len(allocation) == 1 and len(open_holdings) > 1:
        observations.append(
            f"Every holding is the same asset type ({allocation[0]['kind']}), so the "
            f"portfolio has no diversification across asset classes."
        )

    return PortfolioAnalysis(
        total_invested=total_invested,
        current_value=current_value,
        gain=gain,
        gain_pct=round(gain / total_invested * 100, 2) if total_invested > 0 else 0.0,
        monthly_commitment=sum(h.monthly_contribution for h in open_holdings),
        holdings=sorted(open_holdings, key=lambda h: -h.effective_value)
        + [h for h in holdings if h.is_closed],
        allocation=allocation,
        concentrations=concentrations,
        stale_sips=stale_sips,
        maturing_soon=maturing_soon,
        total_debt=total_debt,
        total_emi=total_emi,
        debts=sorted(open_debts, key=lambda d: -d.outstanding)
        + [d for d in debts if d.is_closed],
        net_worth=current_value - total_debt,
        observations=observations,
    )
