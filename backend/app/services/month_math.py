"""Month arithmetic for the reward rules and the health score.

The dashboard's own totals are computed in the frontend (lib/compute.js),
because that is where the spreadsheet's accrual rules have always lived.
The reward engine can't reuse them — a coin has to be awardable without a
browser open — so this module restates *only* the handful of totals the
rules need, using the same conventions:

- a credit-card purchase is an expense on the day it is made; the later
  "CC Repayment" is cash leaving the bank, not a second expense, so it is
  excluded from spend;
- Income is not spend, and Investments are savings rather than
  consumption, so neither counts against a budget.

If those rules ever change, they change in both places — the duplication
is the price of computing rewards server-side, and it is kept to this one
small file on purpose.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Sequence

from app.models import Account, Category, IncomeSource, Transaction

# Transaction types that are not day-to-day spend.
_NOT_SPEND = {"CC Repayment", "Income"}


def month_key(date_str: str) -> str:
    return (date_str or "")[:7]


def prev_month_key(mk: str) -> str:
    year, month = int(mk[:4]), int(mk[5:7])
    return f"{year - 1}-12" if month == 1 else f"{year}-{month - 1:02d}"


def this_month_key(today: date | None = None) -> str:
    d = today or date.today()
    return f"{d.year}-{d.month:02d}"


def days_in_month(mk: str) -> int:
    return monthrange(int(mk[:4]), int(mk[5:7]))[1]


def is_complete(mk: str, today: date | None = None) -> bool:
    """A month can only be judged once it is over — a budget isn't 'kept'
    on the 3rd."""
    return mk < this_month_key(today)


def in_month(txns: Iterable[Transaction], mk: str) -> list[Transaction]:
    return [t for t in txns if month_key(t.date) == mk]


@dataclass(frozen=True)
class MonthTotals:
    spend: float  # accrual spend: everything except repayments and income
    consumption: float  # expenses + loan outflow (the savings denominator)
    txn_income: float  # one-off Income transactions
    investments: float
    wants: float  # discretionary spend, by necessity tag


def aggregate(txns: Sequence[Transaction]) -> MonthTotals:
    spendable = [t for t in txns if t.type not in _NOT_SPEND]
    return MonthTotals(
        spend=sum(t.amount or 0 for t in spendable),
        consumption=sum(t.amount or 0 for t in txns if t.type in {"Expense", "Loan", "Loan Partial"}),
        txn_income=sum(t.amount or 0 for t in txns if t.type == "Income"),
        investments=sum(t.amount or 0 for t in txns if t.type == "Investment"),
        wants=sum(t.amount or 0 for t in spendable if t.necessity == "Want"),
    )


def monthly_income(totals: MonthTotals, sources: Sequence[IncomeSource]) -> float:
    """Recurring salary plus any one-off Income logged that month, so a
    month with no ad-hoc income still has an income figure."""
    recurring = sum(s.monthly_amount or 0 for s in sources if s.active)
    return recurring + totals.txn_income


def debt_outstanding(txns: Sequence[Transaction], accounts: Sequence[Account]) -> float:
    """What the household still owes: unpaid credit-card balances plus the
    remaining principal on loans."""
    total = 0.0
    for account in accounts:
        if account.archived:
            continue
        if account.type == "credit_card":
            spend = sum(
                t.amount or 0
                for t in txns
                if t.payment_mode == "Credit Card"
                and t.provider_type == account.name
                and t.type != "CC Repayment"
            )
            repaid = sum(
                t.amount or 0
                for t in txns
                if t.type == "CC Repayment" and t.account == account.name
            )
            total += max(0.0, (account.opening_balance or 0) + spend - repaid)
        elif account.type == "loan":
            paid = sum(
                t.amount or 0
                for t in txns
                if t.type in {"Loan", "Loan Partial"} and t.account == account.name
            )
            total += max(0.0, (account.opening_balance or 0) - paid)
    return total


def category_ids_named(categories: Sequence[Category], names: set[str]) -> set[int]:
    """Resolve category *names* (as spelled in services.defaults) to this
    household's ids. A renamed or deleted category simply drops out of
    scope rather than breaking the rule that referenced it."""
    return {c.id for c in categories if c.name.casefold() in names and c.id is not None}


def spend_in_categories(txns: Sequence[Transaction], category_ids: set[int]) -> float:
    return sum(
        t.amount or 0
        for t in txns
        if t.type == "Expense" and t.category_id is not None and t.category_id in category_ids
    )
