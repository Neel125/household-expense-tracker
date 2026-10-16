"""Month arithmetic and the accrual rules every other analysis depends on.

These rules are a restatement of `backend/app/services/month_math.py`,
which is itself a restatement of the frontend's `lib/compute.js`. The
duplication is deliberate and bounded: the agent runs in its own
container and cannot import the backend, and a number the agent quotes
has to agree with the number on the user's dashboard or the whole
service is worse than useless.

The rules, in full:

- A credit-card purchase is an expense on the **day it is made**. The
  later `CC Repayment` is cash leaving a bank account to settle it, not a
  second expense, so it never counts as spend.
- `Income` is not spend.
- `Investment Withdrawal` is money coming back from a holding: it credits
  a bank account but is not household income and is not spend.
- `Investment` is savings rather than consumption, so it does not count
  against a budget — but it *is* money that left the current account, so
  cash-flow views count it separately.

If those rules change, they change in three places. Keeping this file
small is what keeps that affordable.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Optional, Sequence

from app.data.models import (
    CONSUMPTION_TYPES,
    NOT_SPEND,
    TYPE_EXPENSE,
    TYPE_INCOME,
    TYPE_INVESTMENT,
    Transaction,
)

MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


# ------------------------------------------------------------ month keys
def month_key(value: str) -> str:
    """'2026-08-14' -> '2026-08'. Blank in, blank out."""
    return (value or "")[:7]


def this_month_key(today: Optional[date] = None) -> str:
    d = today or date.today()
    return f"{d.year}-{d.month:02d}"


def shift_month(mk: str, months: int) -> str:
    """Move a month key forwards or backwards. Handles year rollover in
    both directions, which is the only thing that ever goes wrong here."""
    year, month = int(mk[:4]), int(mk[5:7])
    index = year * 12 + (month - 1) + months
    return f"{index // 12}-{index % 12 + 1:02d}"


def prev_month_key(mk: str) -> str:
    return shift_month(mk, -1)


def next_month_key(mk: str) -> str:
    return shift_month(mk, 1)


def recent_month_keys(mk: str, count: int) -> list[str]:
    """`count` months ending at `mk`, oldest first."""
    return [shift_month(mk, -offset) for offset in range(count - 1, -1, -1)]


def days_in_month(mk: str) -> int:
    return monthrange(int(mk[:4]), int(mk[5:7]))[1]


def month_label(mk: str) -> str:
    return f"{MONTH_NAMES[int(mk[5:7]) - 1]} {mk[:4]}"


def is_complete(mk: str, today: Optional[date] = None) -> bool:
    """A month can only be judged once it is over — a budget is not
    'kept' on the 3rd."""
    return mk < this_month_key(today)


def days_elapsed(mk: str, today: Optional[date] = None) -> int:
    """How far into `mk` we are. A past month is fully elapsed; a future
    month has not started."""
    d = today or date.today()
    current = this_month_key(d)
    if mk < current:
        return days_in_month(mk)
    if mk > current:
        return 0
    return d.day


def parse_date(value: str) -> Optional[date]:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def add_months(day: date, months: int) -> date:
    """Calendar-safe month addition: the 31st plus one month lands on the
    last day of the shorter month rather than raising."""
    index = day.year * 12 + (day.month - 1) + months
    year, month = index // 12, index % 12 + 1
    return day.replace(year=year, month=month, day=min(day.day, monthrange(year, month)[1]))


def in_month(txns: Iterable[Transaction], mk: str) -> list[Transaction]:
    return [t for t in txns if month_key(t.date) == mk]


def between(txns: Iterable[Transaction], start: date, end: date) -> list[Transaction]:
    return [
        t
        for t in txns
        if (parsed := parse_date(t.date)) is not None and start <= parsed <= end
    ]


# --------------------------------------------------------------- totals
@dataclass(frozen=True)
class MonthTotals:
    """One month, reduced to the handful of figures everything else is
    built from. Every field is rupees."""

    month: str
    spend: float           # accrual spend: everything bar repayments and income
    consumption: float     # expenses + loan outflow — the savings denominator
    expenses: float        # Expense rows only
    loan_payments: float
    investments: float
    txn_income: float      # one-off Income rows
    needs: float
    wants: float
    transaction_count: int

    def as_dict(self) -> dict:
        return {
            "month": self.month,
            "label": month_label(self.month),
            "spend": round(self.spend, 2),
            "consumption": round(self.consumption, 2),
            "expenses": round(self.expenses, 2),
            "loanPayments": round(self.loan_payments, 2),
            "investments": round(self.investments, 2),
            "oneOffIncome": round(self.txn_income, 2),
            "needs": round(self.needs, 2),
            "wants": round(self.wants, 2),
            "transactionCount": self.transaction_count,
        }


def aggregate(txns: Sequence[Transaction], mk: str = "") -> MonthTotals:
    spendable = [t for t in txns if t.type not in NOT_SPEND]
    return MonthTotals(
        month=mk,
        spend=sum(t.amount or 0 for t in spendable),
        consumption=sum(t.amount or 0 for t in txns if t.type in CONSUMPTION_TYPES),
        expenses=sum(t.amount or 0 for t in txns if t.type == TYPE_EXPENSE),
        loan_payments=sum(
            t.amount or 0 for t in txns if t.type in CONSUMPTION_TYPES and t.type != TYPE_EXPENSE
        ),
        investments=sum(t.amount or 0 for t in txns if t.type == TYPE_INVESTMENT),
        txn_income=sum(t.amount or 0 for t in txns if t.type == TYPE_INCOME),
        needs=sum(t.amount or 0 for t in spendable if t.necessity == "Need"),
        wants=sum(t.amount or 0 for t in spendable if t.necessity == "Want"),
        transaction_count=len(txns),
    )


def totals_for(txns: Sequence[Transaction], mk: str) -> MonthTotals:
    return aggregate(in_month(txns, mk), mk)


def month_income(totals: MonthTotals, recurring_monthly: float) -> float:
    """Recurring salary plus any one-off Income logged that month, so a
    month with no ad-hoc income still has an income figure."""
    return recurring_monthly + totals.txn_income


# ------------------------------------------------------------ statistics
def median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2


def mad(values: Sequence[float]) -> float:
    """Median absolute deviation — the spread measure used throughout the
    anomaly detector. A household's spending is small-n and full of
    genuine one-offs (a wedding gift, an annual premium), and a standard
    deviation lets exactly those outliers inflate the threshold that is
    supposed to catch them. The median does not move."""
    if not values:
        return 0.0
    centre = median(values)
    return median([abs(v - centre) for v in values])


def pct_change(current: float, previous: float) -> Optional[float]:
    """None rather than infinity when there is no base to compare to —
    'up 0% from nothing' and 'up ∞%' are both lies."""
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100, 1)


def day_of_month_or_last(year: int, month: int, day: int) -> date:
    return date(year, month, min(max(day, 1), monthrange(year, month)[1]))


def next_occurrence(day_of_month: int, after: date) -> date:
    """The next time a monthly commitment falling on `day_of_month` comes
    round, strictly after `after`."""
    candidate = day_of_month_or_last(after.year, after.month, day_of_month)
    if candidate <= after:
        following = add_months(date(after.year, after.month, 1), 1)
        candidate = day_of_month_or_last(following.year, following.month, day_of_month)
    return candidate


def days_until(target: Optional[date], today: date) -> Optional[int]:
    if target is None:
        return None
    return (target - today).days


def iso(day: Optional[date]) -> str:
    return day.isoformat() if day else ""


__all__ = [
    "MonthTotals", "MONTH_NAMES", "add_months", "aggregate", "between",
    "day_of_month_or_last", "days_elapsed", "days_in_month", "days_until",
    "in_month", "is_complete", "iso", "mad", "median", "month_income",
    "month_key", "month_label", "next_month_key", "next_occurrence",
    "parse_date", "pct_change", "prev_month_key", "recent_month_keys",
    "shift_month", "this_month_key", "totals_for", "timedelta",
]
