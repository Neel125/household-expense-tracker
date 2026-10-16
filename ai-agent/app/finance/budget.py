"""Capability 3 — track monthly budgets.

The household sets one monthly envelope and splits it across categories
by percentage (`Household.monthly_budget` × `CategoryBudget.percentage`),
which is the backend's model and is restated here rather than reinvented.

The judgement this module adds over a plain "spent vs allotted" bar is
**pace**. On the 10th of the month, having used 40% of the grocery budget
is not overspending — it is 8 points ahead of schedule, and whether that
matters depends on how the rest of the month usually looks. So every
category reports:

- what is spent and what is left;
- the *expected* share of the budget to have used by today, pro-rated by
  days elapsed;
- a straight-line projection of where the month lands if the current
  daily rate holds;
- a status derived from the projection rather than from today's total,
  because a bar that only turns red on the last day is a report, not a
  warning.

A past month is judged on its final numbers; the pace maths only applies
to a month still running.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from app.data.models import TYPE_EXPENSE
from app.data.snapshot import HouseholdSnapshot
from app.finance.month import (
    days_elapsed,
    days_in_month,
    in_month,
    is_complete,
    month_label,
    pct_change,
    prev_month_key,
    this_month_key,
    totals_for,
)

# How far past its pro-rated share a category may run before it is called
# out. Household spending is lumpy — the month's groceries arrive in
# three shops, not in thirty daily instalments — so a tight band here
# produces an alarm every month and gets ignored.
PACE_TOLERANCE_PCT = 15.0


@dataclass(frozen=True)
class CategoryBudgetStatus:
    category_id: Optional[int]
    category_name: str
    percentage: float
    allotted: float
    spent: float
    remaining: float
    used_pct: float
    expected_pct: float
    projected: float
    projected_overrun: float
    status: str  # on_track | ahead_of_pace | over_budget | unbudgeted | no_budget
    transaction_count: int

    def as_dict(self) -> dict:
        return {
            "categoryId": self.category_id,
            "categoryName": self.category_name,
            "percentage": round(self.percentage, 2),
            "allotted": round(self.allotted, 2),
            "spent": round(self.spent, 2),
            "remaining": round(self.remaining, 2),
            "usedPct": round(self.used_pct, 1),
            "expectedPct": round(self.expected_pct, 1),
            "projected": round(self.projected, 2),
            "projectedOverrun": round(self.projected_overrun, 2),
            "status": self.status,
            "transactionCount": self.transaction_count,
        }


@dataclass(frozen=True)
class BudgetStatus:
    month: str
    label: str
    is_complete: bool
    days_elapsed: int
    days_total: int
    monthly_budget: float
    allocated_pct: float
    total_spent: float
    remaining: float
    used_pct: float
    expected_pct: float
    projected: float
    projected_overrun: float
    status: str
    daily_rate: float
    safe_daily_rate: float
    vs_last_month_pct: Optional[float]
    categories: list[CategoryBudgetStatus]
    unbudgeted_spend: float

    def as_dict(self) -> dict:
        return {
            "month": self.month,
            "label": self.label,
            "isComplete": self.is_complete,
            "daysElapsed": self.days_elapsed,
            "daysInMonth": self.days_total,
            "monthlyBudget": round(self.monthly_budget, 2),
            "allocatedPct": round(self.allocated_pct, 1),
            "totalSpent": round(self.total_spent, 2),
            "remaining": round(self.remaining, 2),
            "usedPct": round(self.used_pct, 1),
            "expectedPct": round(self.expected_pct, 1),
            "projected": round(self.projected, 2),
            "projectedOverrun": round(self.projected_overrun, 2),
            "status": self.status,
            "dailyRateSoFar": round(self.daily_rate, 2),
            "safeDailyRateForRest": round(self.safe_daily_rate, 2),
            "vsLastMonthPct": self.vs_last_month_pct,
            "unbudgetedSpend": round(self.unbudgeted_spend, 2),
            "categories": [c.as_dict() for c in self.categories],
        }


def _status_for(allotted: float, spent: float, projected: float, expected_pct: float,
                used_pct: float) -> str:
    if allotted <= 0:
        return "unbudgeted" if spent > 0 else "no_budget"
    if spent > allotted:
        return "over_budget"
    if projected > allotted:
        return "ahead_of_pace"
    if used_pct > expected_pct + PACE_TOLERANCE_PCT:
        return "ahead_of_pace"
    return "on_track"


def status(snapshot: HouseholdSnapshot, mk: Optional[str] = None) -> BudgetStatus:
    mk = mk or this_month_key(snapshot.as_of)
    complete = is_complete(mk, snapshot.as_of)
    total_days = days_in_month(mk)
    elapsed = max(1, days_elapsed(mk, snapshot.as_of))

    # A finished month is judged on what happened; only a running month
    # gets extrapolated.
    def project(spent: float) -> float:
        if complete or elapsed >= total_days:
            return spent
        return spent / elapsed * total_days

    budget = snapshot.monthly_budget
    # Pro-rated share of the month that has gone by. A complete month is
    # 100% elapsed by definition.
    expected_pct = 100.0 if complete else min(100.0, elapsed / total_days * 100)

    rows = in_month(snapshot.transactions, mk)
    spent_by_category: dict[Optional[int], float] = defaultdict(float)
    count_by_category: dict[Optional[int], int] = defaultdict(int)
    for txn in rows:
        if txn.type == TYPE_EXPENSE:
            spent_by_category[txn.category_id] += float(txn.amount or 0)
            count_by_category[txn.category_id] += 1

    percentage_by_category = {
        b.category_id: float(b.percentage or 0) for b in snapshot.category_budgets
    }

    categories: list[CategoryBudgetStatus] = []
    # Every budgeted category, plus any category that saw spend without
    # one — money spent outside the plan is the thing most worth seeing.
    considered = set(percentage_by_category) | set(spent_by_category)
    for category_id in considered:
        percentage = percentage_by_category.get(category_id, 0.0)
        allotted = budget * percentage / 100
        spent = spent_by_category.get(category_id, 0.0)
        projected = project(spent)
        used_pct = spent / allotted * 100 if allotted > 0 else 0.0
        categories.append(
            CategoryBudgetStatus(
                category_id=category_id,
                category_name=snapshot.category_name(category_id),
                percentage=percentage,
                allotted=allotted,
                spent=spent,
                remaining=allotted - spent,
                used_pct=used_pct,
                expected_pct=expected_pct,
                projected=projected,
                projected_overrun=max(0.0, projected - allotted) if allotted > 0 else 0.0,
                status=_status_for(allotted, spent, projected, expected_pct, used_pct),
                transaction_count=count_by_category.get(category_id, 0),
            )
        )
    # Worst first: over budget before ahead of pace, and within a status,
    # the biggest rupee overrun.
    categories.sort(key=lambda c: (-c.projected_overrun, -c.spent))

    totals = totals_for(snapshot.transactions, mk)
    spent_total = totals.spend
    projected_total = project(spent_total)
    used_pct_total = spent_total / budget * 100 if budget > 0 else 0.0
    remaining_days = max(0, total_days - elapsed)

    previous = totals_for(snapshot.transactions, prev_month_key(mk))

    return BudgetStatus(
        month=mk,
        label=month_label(mk),
        is_complete=complete,
        days_elapsed=elapsed,
        days_total=total_days,
        monthly_budget=budget,
        allocated_pct=sum(percentage_by_category.values()),
        total_spent=spent_total,
        remaining=budget - spent_total,
        used_pct=used_pct_total,
        expected_pct=expected_pct,
        projected=projected_total,
        projected_overrun=max(0.0, projected_total - budget) if budget > 0 else 0.0,
        status=_status_for(budget, spent_total, projected_total, expected_pct, used_pct_total),
        daily_rate=spent_total / elapsed,
        # What is left, spread over the days that are left. The single
        # most actionable number on the page.
        safe_daily_rate=(
            max(0.0, budget - spent_total) / remaining_days
            if budget > 0 and remaining_days > 0
            else 0.0
        ),
        vs_last_month_pct=pct_change(spent_total, previous.spend),
        categories=categories,
        unbudgeted_spend=sum(c.spent for c in categories if c.percentage <= 0),
    )
