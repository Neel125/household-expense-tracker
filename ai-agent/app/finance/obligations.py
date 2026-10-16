"""Capabilities 6 and 7 — monitor standing commitments, and identify the
bills that are about to land.

They are one module because they are one question asked over two
horizons: *what does this household owe, and when?* Six sources answer
it, and none of them is a guess about behaviour — every item here is
something already agreed to:

- **Recurring payments** inferred from the ledger (rent, broadband,
  subscriptions), with the day of the month they usually fall on.
- **Loan EMIs**, dated from the loan's own start day rather than from the
  pattern, because that is the contractual date.
- **SIP and RD instalments**, from the monthly contribution the user
  recorded against the holding.
- **Deposits maturing** — an FD or RD reaching maturity is not a bill but
  it is a decision with a deadline, and missing it means the money sits
  in a sweep account earning nothing.
- **Credit-card balances**, computed with the app's accrual rules: card
  purchases accrue on the day they are made and repayments settle them.
- **Vehicle papers** — insurance, PUC and fitness expiries are dated,
  unavoidable and expensive to miss, and the household already records
  them.

Everything is returned with `daysUntil` so the caller can window it, and
with the source that produced it so a user who disagrees knows which
record to correct.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.data.models import (
    MATURING_INVESTMENT_KINDS,
    RECURRING_INVESTMENT_KINDS,
    TYPE_CC_REPAYMENT,
)
from app.data.snapshot import HouseholdSnapshot
from app.finance.naming import suffixed
from app.finance.month import (
    next_occurrence,
    parse_date,
    this_month_key,
)
from app.finance.recurring import covered_by_record, record_names
from app.finance.recurring import detect as detect_recurring

DEFAULT_HORIZON_DAYS = 45
# Papers within this window need renewing; the amount is unknown, so
# these carry a due date without one.
PAPER_HORIZON_DAYS = 60

SEVERITY_ORDER = {"overdue": 0, "high": 1, "medium": 2, "low": 3}


@dataclass(frozen=True)
class Obligation:
    kind: str  # recurring | emi | sip | maturity | credit_card | vehicle_paper
    label: str
    amount: Optional[float]  # None when the amount is genuinely not known
    due_date: str
    days_until: Optional[int]
    severity: str
    source: str
    detail: str
    category_name: str = ""

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "amount": round(self.amount, 2) if self.amount is not None else None,
            "dueDate": self.due_date,
            "daysUntil": self.days_until,
            "severity": self.severity,
            "source": self.source,
            "detail": self.detail,
            "categoryName": self.category_name,
        }


def _severity(days: Optional[int], amount: Optional[float]) -> str:
    if days is not None and days < 0:
        return "overdue"
    if days is not None and days <= 3:
        return "high"
    if amount is not None and amount >= 10000 and (days is None or days <= 14):
        return "high"
    if days is not None and days <= 10:
        return "medium"
    return "low"


def _emi_due_date(start_date: str, today: date) -> Optional[date]:
    """An EMI falls on the loan's start day, every month. Without a start
    date there is no contractual day to quote, and inventing one would
    put a wrong date in front of the user."""
    start = parse_date(start_date)
    if start is None:
        return None
    return next_occurrence(start.day, today)


def credit_card_balances(snapshot: HouseholdSnapshot) -> list[dict]:
    """What is outstanding on each card, under the app's accrual rules: a
    card purchase counts from the day it is made, and a `CC Repayment`
    against that card settles it. Identical to the backend's
    `month_math.debt_outstanding`."""
    balances: list[dict] = []
    for account in snapshot.credit_cards:
        charged = sum(
            float(t.amount or 0)
            for t in snapshot.transactions
            if t.payment_mode == "Credit Card"
            and t.provider_type == account.name
            and t.type != TYPE_CC_REPAYMENT
        )
        repaid = sum(
            float(t.amount or 0)
            for t in snapshot.transactions
            if t.type == TYPE_CC_REPAYMENT and t.account == account.name
        )
        outstanding = max(0.0, float(account.opening_balance or 0) + charged - repaid)
        this_month = sum(
            float(t.amount or 0)
            for t in snapshot.transactions
            if t.payment_mode == "Credit Card"
            and t.provider_type == account.name
            and t.type != TYPE_CC_REPAYMENT
            and (t.date or "")[:7] == this_month_key(snapshot.as_of)
        )
        balances.append(
            {
                "card": account.name,
                "institution": account.institution,
                "outstanding": round(outstanding, 2),
                "chargedThisMonth": round(this_month, 2),
                "totalCharged": round(charged, 2),
                "totalRepaid": round(repaid, 2),
            }
        )
    return sorted(balances, key=lambda row: -row["outstanding"])


def upcoming(
    snapshot: HouseholdSnapshot, horizon_days: int = DEFAULT_HORIZON_DAYS
) -> list[Obligation]:
    """Every dated commitment inside the horizon, soonest first."""
    today = snapshot.as_of
    found: list[Obligation] = []

    # --- detected recurring payments
    already_paid = {
        (t.merchant or t.name or "").strip().casefold()
        for t in snapshot.transactions
        if (t.date or "")[:7] == this_month_key(today)
    }
    names = record_names(snapshot)
    for item in detect_recurring(snapshot):
        if not item.active or item.days_until is None:
            continue
        if item.days_until > horizon_days:
            continue
        # An EMI or SIP instalment is listed once, from the loan or
        # holding record below — that is the contractual amount and date,
        # where this is only the pattern it leaves in the ledger.
        if covered_by_record(item, names):
            continue
        # Paid already this month and not due again inside the horizon.
        if item.key in already_paid and item.days_until > 20:
            continue
        found.append(
            Obligation(
                kind="recurring",
                label=item.label,
                amount=item.typical_amount,
                due_date=item.next_due,
                days_until=item.days_until,
                severity=_severity(item.days_until, item.typical_amount),
                source="Detected from your transaction history",
                detail=(
                    f"Normally ₹{item.typical_amount:,.0f} around the "
                    f"{item.typical_day}th, seen in {len(item.months_seen)} recent months."
                ),
                category_name=item.category_name,
            )
        )

    # --- loan EMIs
    for debt in snapshot.debts:
        emi = float(debt.emi or 0)
        if emi <= 0 or float(debt.outstanding or 0) <= 0:
            continue
        due = _emi_due_date(debt.start_date, today)
        days = (due - today).days if due else None
        if days is not None and days > horizon_days:
            continue
        found.append(
            Obligation(
                kind="emi",
                label=suffixed(debt.name, "EMI"),
                amount=emi,
                due_date=due.isoformat() if due else "",
                days_until=days,
                severity=_severity(days, emi),
                source=f"Loan record ({debt.lender})" if debt.lender else "Loan record",
                detail=(
                    f"₹{emi:,.0f} a month at {float(debt.annual_rate_pct or 0):.1f}%, "
                    f"₹{float(debt.outstanding or 0):,.0f} still outstanding."
                    + ("" if due else " No start date recorded, so no due date can be given.")
                ),
                category_name="Loan payment",
            )
        )

    # --- SIP and RD instalments
    for holding in snapshot.investments:
        if getattr(holding, "closed", False):
            continue
        contribution = float(holding.monthly_contribution or 0)
        if contribution <= 0 or holding.kind not in RECURRING_INVESTMENT_KINDS:
            continue
        start = parse_date(holding.start_date)
        due = next_occurrence(start.day, today) if start else None
        days = (due - today).days if due else None
        if days is not None and days > horizon_days:
            continue
        found.append(
            Obligation(
                kind="sip",
                label=f"{holding.name} instalment",
                amount=contribution,
                due_date=due.isoformat() if due else "",
                days_until=days,
                severity=_severity(days, contribution),
                source=f"{holding.kind.upper()} record",
                detail=(
                    f"₹{contribution:,.0f} a month into {holding.name}"
                    + (f" at {holding.institution}" if holding.institution else "")
                    + "."
                ),
                category_name="Investment",
            )
        )

    # --- deposits maturing
    for holding in snapshot.investments:
        if getattr(holding, "closed", False):
            continue
        if holding.kind not in MATURING_INVESTMENT_KINDS:
            continue
        maturity = parse_date(holding.maturity_date)
        if maturity is None:
            continue
        days = (maturity - today).days
        if days < 0 or days > horizon_days:
            continue
        value = float(holding.current_value or 0) or float(holding.amount_invested or 0)
        found.append(
            Obligation(
                kind="maturity",
                label=f"{holding.name} matures",
                amount=value or None,
                due_date=holding.maturity_date,
                days_until=days,
                severity="medium" if days <= 14 else "low",
                source=f"{holding.kind.upper()} record",
                detail=(
                    f"{holding.name} matures on {holding.maturity_date}. "
                    f"Decide whether to renew or redeploy it before the bank sweeps it "
                    f"into a low-interest account."
                ),
                category_name="Investment",
            )
        )

    # --- vehicle papers
    for record in snapshot.vehicle_records:
        if record.kind not in ("insurance", "puc", "fitness"):
            continue
        expiry = parse_date(record.expiry_date)
        if expiry is None:
            continue
        days = (expiry - today).days
        if days > min(horizon_days, PAPER_HORIZON_DAYS):
            continue
        vehicle = next((v.name for v in snapshot.vehicles if v.id == record.vehicle_id), "Vehicle")
        found.append(
            Obligation(
                kind="vehicle_paper",
                label=f"{vehicle} {record.kind.upper()} expires",
                # The renewal price is not knowable from the last one, so
                # it is left unstated rather than guessed.
                amount=None,
                due_date=record.expiry_date,
                days_until=days,
                severity="overdue" if days < 0 else ("high" if days <= 14 else "medium"),
                source="Garage record",
                detail=(
                    f"{vehicle}'s {record.kind.upper()} "
                    + (f"expired on {record.expiry_date}" if days < 0
                       else f"expires on {record.expiry_date}")
                    + ". Driving without it is a fine, and a lapsed policy is a much "
                    "larger exposure."
                ),
                category_name="Insurance" if record.kind == "insurance" else "Transport",
            )
        )

    # --- unpaid challans, which are already overdue by definition
    for record in snapshot.vehicle_records:
        if record.kind != "challan" or record.status == "paid":
            continue
        vehicle = next((v.name for v in snapshot.vehicles if v.id == record.vehicle_id), "Vehicle")
        found.append(
            Obligation(
                kind="challan",
                label=f"{vehicle} challan unpaid",
                amount=float(record.amount or 0) or None,
                due_date=record.date,
                days_until=None,
                severity="high",
                source="Garage record",
                detail=(
                    f"{record.title or 'A challan'} on {vehicle} is still marked "
                    f"{record.status or 'unpaid'}."
                ),
                category_name="Transport",
            )
        )

    found.sort(
        key=lambda o: (
            o.days_until if o.days_until is not None else 999,
            SEVERITY_ORDER.get(o.severity, 9),
            -(o.amount or 0),
        )
    )
    return found


def summary(snapshot: HouseholdSnapshot, horizon_days: int = DEFAULT_HORIZON_DAYS) -> dict:
    """Bills, balances and standing commitments in one payload."""
    items = upcoming(snapshot, horizon_days)
    cards = credit_card_balances(snapshot)
    names = record_names(snapshot)
    recurrings = [r for r in detect_recurring(snapshot) if not covered_by_record(r, names)]

    dated_total = sum(o.amount or 0 for o in items if o.days_until is not None)
    next_seven = sum(
        o.amount or 0 for o in items if o.days_until is not None and 0 <= o.days_until <= 7
    )

    return {
        "asOf": snapshot.as_of.isoformat(),
        "horizonDays": horizon_days,
        "totalDue": round(dated_total, 2),
        "dueNextSevenDays": round(next_seven, 2),
        "overdueCount": sum(1 for o in items if o.severity == "overdue"),
        "itemsWithUnknownAmount": sum(1 for o in items if o.amount is None),
        "obligations": [o.as_dict() for o in items],
        "creditCards": cards,
        "creditCardOutstanding": round(sum(c["outstanding"] for c in cards), 2),
        "activeRecurring": [r.as_dict() for r in recurrings if r.active],
        "lapsedRecurring": [r.as_dict() for r in recurrings if not r.active],
        "monthlyCommitted": round(
            sum(r.typical_amount for r in recurrings if r.active), 2
        ),
    }
