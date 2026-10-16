"""Capability 9 — the arithmetic behind recommending actions against the
household's own goals.

The model does the recommending; this module decides what is *true*
first, because the useful part of goal advice is a number, not
encouragement. For every goal it answers:

- how much is still needed, and how many months are left;
- the monthly contribution that would actually get there on time;
- whether that contribution fits in the household's real surplus
  (income minus everything it typically spends and commits);
- and if several goals compete for one surplus, how far the shortfall
  goes.

Two rules of thumb are applied, and both are stated rather than hidden
in a score:

- an **emergency fund** worth three to six months of outgoings comes
  before any other goal, because without it the other goals get raided
  the first time something breaks;
- a **debt costing more than a goal is likely to earn** is paid down
  first. Clearing 14% debt is a guaranteed 14%; no savings goal offers
  that.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Optional

from app.data.snapshot import HouseholdSnapshot
from app.finance.month import (
    is_complete,
    median,
    month_income,
    parse_date,
    recent_month_keys,
    this_month_key,
    totals_for,
)

# Months of outgoings an emergency fund should cover.
EMERGENCY_FUND_MIN_MONTHS = 3.0
EMERGENCY_FUND_TARGET_MONTHS = 6.0
# A debt above this rate outranks saving toward a goal.
DEBT_BEATS_SAVING_PCT = 10.0
LOOKBACK_MONTHS = 6


@dataclass(frozen=True)
class GoalProgress:
    id: int
    name: str
    kind: str
    target_amount: float
    saved_amount: float
    remaining: float
    progress_pct: float
    target_date: str
    months_left: Optional[int]
    required_monthly: Optional[float]
    status: str  # achieved | on_track | at_risk | no_deadline | unfunded | overdue
    detail: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "targetAmount": round(self.target_amount, 2),
            "savedAmount": round(self.saved_amount, 2),
            "remaining": round(self.remaining, 2),
            "progressPct": round(self.progress_pct, 1),
            "targetDate": self.target_date,
            "monthsLeft": self.months_left,
            "requiredMonthly": (
                round(self.required_monthly, 2) if self.required_monthly is not None else None
            ),
            "status": self.status,
            "detail": self.detail,
        }


def monthly_surplus(snapshot: HouseholdSnapshot) -> dict:
    """What is genuinely free each month.

    Taken from *completed* months only — a month still running always
    looks like a surplus because its spending has not all happened yet,
    and a household told it has ₹40,000 spare on the 4th will spend it.
    """
    current = this_month_key(snapshot.as_of)
    window = [m for m in recent_month_keys(current, LOOKBACK_MONTHS + 1) if is_complete(m, snapshot.as_of)]
    recurring_income = snapshot.recurring_monthly_income

    incomes: list[float] = []
    outgoings: list[float] = []
    for mk in window:
        totals = totals_for(snapshot.transactions, mk)
        if totals.transaction_count == 0:
            continue
        incomes.append(month_income(totals, recurring_income))
        # Spend excludes investments already (they are savings, not
        # consumption), so this is the money that has to go out.
        outgoings.append(totals.spend)

    typical_income = median(incomes) if incomes else recurring_income
    typical_outgoing = median(outgoings) if outgoings else 0.0
    return {
        "monthsConsidered": len(outgoings),
        "typicalIncome": round(typical_income, 2),
        "typicalOutgoing": round(typical_outgoing, 2),
        "surplus": round(typical_income - typical_outgoing, 2),
        "savingsRatePct": (
            round((typical_income - typical_outgoing) / typical_income * 100, 1)
            if typical_income > 0
            else 0.0
        ),
    }


def _months_between_today(target: str, snapshot: HouseholdSnapshot) -> Optional[int]:
    """Whole months from today to `target`, negative once it has passed.

    Rounded away from zero: half a month left is still a month that has
    to be funded, and a deadline missed by a fortnight is a month late.
    """
    due = parse_date(target)
    if due is None:
        return None
    days = (due - snapshot.as_of).days
    months = ceil(abs(days) / 30)
    return months if days >= 0 else -months


def progress(snapshot: HouseholdSnapshot) -> list[GoalProgress]:
    rows: list[GoalProgress] = []
    for goal in snapshot.goals:
        target = float(goal.target_amount or 0)
        saved = float(goal.saved_amount or 0)
        remaining = max(0.0, target - saved)
        pct = (saved / target * 100) if target > 0 else 0.0
        months_left = _months_between_today(goal.target_date, snapshot)

        if target <= 0:
            status, required, detail = (
                "unfunded",
                None,
                "No target amount set, so there is nothing to measure against.",
            )
        elif remaining <= 0:
            status, required, detail = (
                "achieved",
                0.0,
                f"Fully funded at ₹{saved:,.0f}.",
            )
        elif months_left is None:
            status, required, detail = (
                "no_deadline",
                None,
                (
                    f"₹{remaining:,.0f} still to go. Without a target date there is no "
                    f"monthly figure to aim at — setting one is what makes this goal "
                    f"actionable."
                ),
            )
        elif months_left < 0:
            status, required, detail = (
                "overdue",
                remaining,
                (
                    f"The target date of {goal.target_date} has passed with "
                    f"₹{remaining:,.0f} still unfunded."
                ),
            )
        elif months_left == 0:
            status, required, detail = (
                "at_risk",
                remaining,
                f"Due this month with ₹{remaining:,.0f} still to find.",
            )
        else:
            required = remaining / months_left
            status = "on_track"
            detail = (
                f"₹{remaining:,.0f} over {months_left} month(s) means "
                f"₹{required:,.0f} a month."
            )

        rows.append(
            GoalProgress(
                id=goal.id or 0,
                name=goal.name,
                kind=goal.kind,
                target_amount=target,
                saved_amount=saved,
                remaining=remaining,
                progress_pct=min(100.0, pct),
                target_date=goal.target_date,
                months_left=months_left,
                required_monthly=required,
                status=status,
                detail=detail,
            )
        )

    # Soonest deadline first; goals without one come last.
    rows.sort(key=lambda g: (g.months_left is None, g.months_left if g.months_left is not None else 0))
    return rows


def emergency_fund(snapshot: HouseholdSnapshot, surplus: dict) -> dict:
    """Where the household stands on the goal that comes before the rest."""
    outgoing = float(surplus["typicalOutgoing"])
    fund = next(
        (g for g in snapshot.goals if g.kind == "emergency"),
        None,
    )
    held = float(fund.saved_amount or 0) if fund else 0.0
    months_covered = held / outgoing if outgoing > 0 else 0.0
    minimum = outgoing * EMERGENCY_FUND_MIN_MONTHS
    target = outgoing * EMERGENCY_FUND_TARGET_MONTHS

    if not fund:
        status = "not_set"
    elif months_covered >= EMERGENCY_FUND_TARGET_MONTHS:
        status = "funded"
    elif months_covered >= EMERGENCY_FUND_MIN_MONTHS:
        status = "adequate"
    else:
        status = "short"

    return {
        "exists": fund is not None,
        "held": round(held, 2),
        "monthsCovered": round(months_covered, 1),
        "minimumRecommended": round(minimum, 2),
        "targetRecommended": round(target, 2),
        "shortfallToMinimum": round(max(0.0, minimum - held), 2),
        "status": status,
        "basis": (
            f"Based on a typical ₹{outgoing:,.0f} of monthly outgoings over the last "
            f"{surplus['monthsConsidered']} completed month(s)."
        ),
    }


def analyse(snapshot: HouseholdSnapshot) -> dict:
    """Goals, the money available for them, and the two structural rules
    that outrank them."""
    surplus = monthly_surplus(snapshot)
    rows = progress(snapshot)
    fund = emergency_fund(snapshot, surplus)

    committed_to_goals = sum(
        g.required_monthly or 0 for g in rows if g.status in ("on_track", "at_risk", "overdue")
    )
    available = float(surplus["surplus"])
    shortfall = max(0.0, committed_to_goals - available)

    # Debts that outrank saving, worst rate first.
    expensive_debt = sorted(
        (
            {
                "name": d.name,
                "outstanding": round(float(d.outstanding or 0), 2),
                "ratePct": round(float(d.annual_rate_pct or 0), 2),
                "emi": round(float(d.emi or 0), 2),
            }
            for d in snapshot.debts
            if float(d.outstanding or 0) > 0
            and float(d.annual_rate_pct or 0) >= DEBT_BEATS_SAVING_PCT
        ),
        key=lambda row: -row["ratePct"],
    )

    return {
        "surplus": surplus,
        "emergencyFund": fund,
        "goals": [g.as_dict() for g in rows],
        "totalRequiredMonthly": round(committed_to_goals, 2),
        "availableMonthly": round(available, 2),
        "monthlyShortfall": round(shortfall, 2),
        "feasible": shortfall <= 0,
        "expensiveDebt": expensive_debt,
        "priorityRules": [
            (
                f"An emergency fund covering {EMERGENCY_FUND_MIN_MONTHS:.0f}–"
                f"{EMERGENCY_FUND_TARGET_MONTHS:.0f} months of outgoings comes before "
                f"other goals; without it the first emergency raids them."
            ),
            (
                f"Debt above {DEBT_BEATS_SAVING_PCT:.0f}% is paid down before saving "
                f"toward a goal — clearing it is a guaranteed return at that rate."
            ),
        ],
    }
