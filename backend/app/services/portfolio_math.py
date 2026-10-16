"""Portfolio arithmetic: what a linked transaction does to a holding.

Two questions, both answered here and nowhere else:

- **Investments.** What has actually gone in? Every `Investment`-type
  transaction linked to a holding is a contribution, so the invested
  total is the opening figure plus those contributions. Where the return
  rate is known, each contribution is also grown from its own date to
  today, which gives a projected value for products whose worth is
  arithmetic (FD, RD) and a sanity estimate for those whose worth is the
  market's opinion (SIP, stocks) until the user types the real number.

- **Debts.** How much of an EMI was interest and how much actually paid
  the loan down? Reducing-balance amortisation over the linked `Loan`
  transactions in date order: interest accrues on the balance for the
  time since the previous payment, and whatever the payment covers
  beyond that reduces the principal. A `Loan Partial` row is different:
  the whole amount reduces principal, which is what a prepayment does.

Everything is **derived, never stored**. The alternative — mutating a
balance on each write — needs a per-transaction record of what was
applied so an edit or delete can be undone, and still gets the interest
split wrong when a payment is back-dated, because interest depends on
the balance *at the time*. Replaying the payments in date order is the
only way to be right about both, and it self-heals: correct a
transaction and every figure downstream is correct on the next read.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Sequence

from app.models import Debt, Investment, Transaction
from app.models.transaction import TYPE_LOAN, TYPE_LOAN_PARTIAL

# Average days in a month over a 400-year cycle. Used to turn a gap
# between two payment dates into "months of interest".
DAYS_PER_MONTH = 30.4375
# A gap longer than this is almost certainly a data-entry artefact (a
# payment back-dated years, or a long tracking gap), so interest accrual
# is capped rather than producing a shock number.
MAX_ACCRUAL_MONTHS = 12.0


def _parse(value: str) -> Optional[date]:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def _months_between(start: Optional[date], end: Optional[date]) -> float:
    if not start or not end or end <= start:
        return 0.0
    return (end - start).days / DAYS_PER_MONTH


def _grow(amount: float, annual_rate_pct: float, months: float) -> float:
    """Compound `amount` monthly for `months`. A zero rate is the identity,
    which is what an unrated holding should do — no invented growth."""
    if amount <= 0 or annual_rate_pct <= 0 or months <= 0:
        return max(0.0, amount)
    return amount * (1 + annual_rate_pct / 100 / 12) ** months


def by_date(txns: Sequence[Transaction]) -> list[Transaction]:
    """Chronological, with the row id as the tie-break so two payments on
    the same day always amortise in a stable order."""
    return sorted(txns, key=lambda t: ((t.date or ""), t.id or 0))


# ------------------------------------------------------------- investments
@dataclass(frozen=True)
class Contribution:
    transaction_id: int
    date: str
    name: str
    amount: float
    # What this contribution is worth today at the holding's return rate.
    grown_to: float


@dataclass(frozen=True)
class InvestmentView:
    opening_invested: float
    contributed: float
    total_invested: float
    projected_value: float
    # The number to actually show: the user's own valuation when they have
    # entered one, else the projection.
    effective_value: float
    value_is_manual: bool
    gain: float
    gain_pct: float
    # Set when the holding is closed: what it was worth at close, so the
    # row can still show a figure after effective_value has been zeroed
    # (otherwise net worth would count both the bank credit and the asset).
    closed_value: float = 0
    is_closed: bool = False
    contributions: list[Contribution] = field(default_factory=list)

    @property
    def contribution_count(self) -> int:
        return len(self.contributions)

    @property
    def last_contribution_date(self) -> str:
        return self.contributions[-1].date if self.contributions else ""


def view_investment(
    investment: Investment,
    linked: Sequence[Transaction],
    today: Optional[date] = None,
) -> InvestmentView:
    day = today or date.today()
    rate = float(investment.annual_return_pct or 0)

    # `amount_invested` is the figure the user maintained by hand before
    # any transaction was linked, so it is treated as the opening balance
    # and linked contributions stack on top. Both halves are reported
    # separately, so a contribution accidentally counted in the opening
    # figure too is visible rather than hidden.
    opening = max(0.0, float(investment.amount_invested or 0))
    opening_from = _parse(investment.start_date) or _parse(investment.created_at)
    projected = _grow(opening, rate, _months_between(opening_from, day))

    contributions: list[Contribution] = []
    contributed = 0.0
    for txn in by_date(linked):
        amount = max(0.0, float(txn.amount or 0))
        grown = _grow(amount, rate, _months_between(_parse(txn.date), day))
        contributed += amount
        projected += grown
        contributions.append(
            Contribution(
                transaction_id=txn.id or 0,
                date=txn.date or "",
                name=txn.name or "",
                amount=amount,
                grown_to=round(grown, 2),
            )
        )

    total_invested = opening + contributed
    manual = float(investment.current_value or 0)
    value_is_manual = manual > 0
    live_value = manual if value_is_manual else projected
    closed = bool(getattr(investment, "closed", False))
    # Closed holdings are no longer assets — the proceeds sit in a bank
    # (or in a successor holding). Keep the pre-close figure on the view
    # so the row can say what was withdrawn.
    effective = 0.0 if closed else live_value
    closed_value = live_value if closed else 0.0
    gain_from = closed_value if closed else effective
    gain = gain_from - total_invested
    return InvestmentView(
        opening_invested=round(opening, 2),
        contributed=round(contributed, 2),
        total_invested=round(total_invested, 2),
        projected_value=round(projected, 2),
        effective_value=round(effective, 2),
        value_is_manual=value_is_manual and not closed,
        gain=round(gain, 2),
        gain_pct=round(gain / total_invested * 100, 2) if total_invested > 0 else 0.0,
        closed_value=round(closed_value, 2),
        is_closed=closed,
        contributions=contributions,
    )


# -------------------------------------------------------------------- debts
@dataclass(frozen=True)
class Instalment:
    transaction_id: int
    date: str
    name: str
    paid: float
    interest: float
    principal: float
    # Balance left after this payment.
    balance: float
    # Months of interest this payment carried, so an early prepayment
    # (which accrues almost none) is explainable in the UI.
    accrued_months: float
    # emi | prepay — a partial payment skips the interest split.
    kind: str = "emi"


@dataclass(frozen=True)
class DebtView:
    opening_outstanding: float
    principal_repaid: float
    interest_paid: float
    total_paid: float
    outstanding: float
    emis_paid: float  # baseline months_paid + linked payments
    is_closed: bool
    payoff_pct: float
    instalments: list[Instalment] = field(default_factory=list)

    @property
    def last_payment_date(self) -> str:
        return self.instalments[-1].date if self.instalments else ""


def view_debt(
    debt: Debt,
    linked: Sequence[Transaction],
    today: Optional[date] = None,
) -> DebtView:
    rate = float(debt.annual_rate_pct or 0)
    # As with investments, the hand-maintained `outstanding` is the
    # opening balance and linked EMIs pay it down from there.
    balance = max(0.0, float(debt.outstanding or 0))
    opening = balance

    instalments: list[Instalment] = []
    principal_repaid = 0.0
    interest_paid = 0.0
    previous: Optional[date] = None

    for txn in by_date(linked):
        paid = max(0.0, float(txn.amount or 0))
        when = _parse(txn.date)
        is_prepay = (txn.type or "") == TYPE_LOAN_PARTIAL
        if is_prepay:
            # The whole amount reduces principal. Interest for the days
            # since the last EMI is left for the next EMI to pick up on
            # the new (lower) balance.
            months = 0.0
            interest = 0.0
            principal = min(paid, balance)
        else:
            # The first linked EMI is assumed to be one ordinary period's
            # worth of interest: the opening balance is "as of now", not
            # as of the loan's start date, so accruing from start_date
            # would invent years of interest that has already been paid.
            months = 1.0 if previous is None else min(
                MAX_ACCRUAL_MONTHS, _months_between(previous, when)
            )
            interest = balance * (rate / 100 / 12) * months if rate > 0 and balance > 0 else 0.0
            interest = min(interest, paid)
            # A payment smaller than the interest due pays no principal.
            # Real loans grow in that case; we hold the balance flat
            # instead of reporting a debt that goes up when you pay it.
            principal = min(max(0.0, paid - interest), balance)
        balance -= principal
        principal_repaid += principal
        interest_paid += interest
        previous = when or previous
        instalments.append(
            Instalment(
                transaction_id=txn.id or 0,
                date=txn.date or "",
                name=txn.name or "",
                paid=round(paid, 2),
                interest=round(interest, 2),
                principal=round(principal, 2),
                balance=round(balance, 2),
                accrued_months=round(months, 2),
                kind="prepay" if is_prepay else "emi",
            )
        )

    emi_count = sum(1 for t in linked if (t.type or "") == TYPE_LOAN)
    emis_paid = float(debt.months_paid or 0) + emi_count
    total_borrowed = float(debt.principal or 0)
    # "Closed" has to cover both ways a loan ends: EMIs amortising the
    # balance to zero, and the user editing the outstanding to zero
    # because they settled it outside the app. Requiring a real loan
    # (a principal, or something outstanding when tracking began) is what
    # keeps an empty placeholder row from counting as paid off.
    existed = total_borrowed > 0 or opening > 0
    # Progress against the original loan where the principal is known,
    # else against what tracking started with.
    denominator = total_borrowed if total_borrowed > 0 else opening
    return DebtView(
        opening_outstanding=round(opening, 2),
        principal_repaid=round(principal_repaid, 2),
        interest_paid=round(interest_paid, 2),
        total_paid=round(principal_repaid + interest_paid, 2),
        outstanding=round(balance, 2),
        emis_paid=emis_paid,
        is_closed=balance <= 0.005 and existed,
        payoff_pct=(
            round(max(0.0, min(100.0, (denominator - balance) / denominator * 100)), 2)
            if denominator > 0
            else 0.0
        ),
        instalments=instalments,
    )
