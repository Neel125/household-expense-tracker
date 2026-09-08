"""The Financial Health Score.

Deliberately measures *behaviour*, not wealth: every component is a ratio
the household controls (spend against its own budget, savings against its
own income, days tracked against days elapsed), so a family on a small
income can score 90 and a high earner who overspends can score 40. The
reward engine then pays for *improvement* in this number rather than for
its level — see RewardsService.settle.

A component that cannot be judged yet (no budget set, no income recorded)
returns None and is left out of the average instead of scoring zero, so a
half-configured household isn't told it is unhealthy.
"""
import json
from dataclasses import dataclass
from datetime import date
from typing import Optional

from sqlmodel import Session

from app.models import HealthSnapshot
from app.models.mixins import now_iso
from app.repositories.repositories import (
    AccountRepository,
    GoalRepository,
    HealthSnapshotRepository,
    HouseholdRepo,
    IncomeSourceRepository,
    TransactionRepository,
)
from app.services import month_math
from app.services.errors import NotFoundError

# How many months of consumption a fully-funded emergency fund covers.
EMERGENCY_FUND_MONTHS = 3
# Savings rate that scores a perfect 100.
TARGET_SAVINGS_RATE = 0.30
# Debt above half of annual income scores zero.
MAX_HEALTHY_DEBT_RATIO = 0.5


def _clamp(value: float) -> int:
    return int(max(0, min(100, round(value))))


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    score: Optional[int]  # None = not enough data to judge
    detail: str


@dataclass(frozen=True)
class HealthReport:
    month: str
    score: int
    components: list[Component]

    def as_dict(self) -> dict[str, int]:
        return {c.key: c.score for c in self.components if c.score is not None}


class HealthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.households = HouseholdRepo(session)
        self.transactions = TransactionRepository(session)
        self.accounts = AccountRepository(session)
        self.income_sources = IncomeSourceRepository(session)
        self.goals = GoalRepository(session)
        self.snapshots = HealthSnapshotRepository(session)

    # --------------------------------------------------------------- report
    def report(self, household_id: int, mk: Optional[str] = None) -> HealthReport:
        household = self.households.get(household_id)
        if not household:
            raise NotFoundError("Household not found")
        mk = mk or month_math.this_month_key()

        all_txns = list(self.transactions.list(household_id))
        month_txns = month_math.in_month(all_txns, mk)
        totals = month_math.aggregate(month_txns)
        sources = list(self.income_sources.list(household_id))
        income = month_math.monthly_income(totals, sources)

        components = [
            self._budget(household.monthly_budget or 0, totals.spend),
            self._savings(income, totals.consumption),
            self._tracking(month_txns, mk),
            self._debt(all_txns, income, household_id),
            self._emergency(household_id, all_txns, mk),
        ]
        judged = [c.score for c in components if c.score is not None]
        overall = _clamp(sum(judged) / len(judged)) if judged else 0
        return HealthReport(month=mk, score=overall, components=components)

    # ----------------------------------------------------------- components
    @staticmethod
    def _budget(budget: float, spend: float) -> Component:
        if budget <= 0:
            return Component("budget", "Budget discipline", None, "No monthly budget set yet")
        ratio = spend / budget
        # Comfortably inside the envelope is full marks; 30% over is zero.
        score = _clamp(100 * (1.3 - ratio) / (1.3 - 0.85))
        return Component("budget", "Budget discipline", score, f"{round(ratio * 100)}% of budget used")

    @staticmethod
    def _savings(income: float, consumption: float) -> Component:
        if income <= 0:
            return Component("savings", "Savings", None, "No income recorded for this month")
        rate = (income - consumption) / income
        score = _clamp(rate / TARGET_SAVINGS_RATE * 100)
        return Component("savings", "Savings", score, f"{round(rate * 100)}% of income saved")

    @staticmethod
    def _tracking(month_txns: list, mk: str) -> Component:
        total_days = month_math.days_in_month(mk)
        today = date.today()
        elapsed = today.day if mk == month_math.this_month_key(today) else total_days
        elapsed = max(1, min(elapsed, total_days))
        tracked = len({t.date for t in month_txns if t.date})
        score = _clamp(tracked / elapsed * 100)
        return Component(
            "tracking",
            "Expense tracking",
            score,
            f"{tracked} of {elapsed} day(s) logged",
        )

    def _debt(self, all_txns: list, income: float, household_id: int) -> Component:
        accounts = list(self.accounts.list(household_id))
        debt = month_math.debt_outstanding(all_txns, accounts)
        if debt <= 0:
            return Component("debt", "Debt management", 100, "No outstanding debt")
        if income <= 0:
            return Component("debt", "Debt management", None, "No income recorded to compare against")
        ratio = debt / (income * 12)
        score = _clamp(100 * (1 - ratio / MAX_HEALTHY_DEBT_RATIO))
        return Component(
            "debt",
            "Debt management",
            score,
            f"Owe {round(ratio * 100)}% of a year's income",
        )

    def _emergency(self, household_id: int, all_txns: list, mk: str) -> Component:
        funds = [g for g in self.goals.list(household_id) if g.kind == "emergency"]
        if not funds:
            months = self._avg_monthly_consumption(all_txns, mk)
            hint = (
                f"Create an emergency-fund goal (about "
                f"{round(months * EMERGENCY_FUND_MONTHS):,} covers "
                f"{EMERGENCY_FUND_MONTHS} months)"
                if months > 0
                else "Create an emergency-fund goal"
            )
            return Component("emergency", "Emergency fund", 0, hint)
        saved = sum(g.saved_amount or 0 for g in funds)
        target = sum(g.target_amount or 0 for g in funds)
        if target <= 0:
            return Component("emergency", "Emergency fund", None, "Emergency goal has no target")
        score = _clamp(saved / target * 100)
        return Component("emergency", "Emergency fund", score, f"{score}% of target funded")

    @staticmethod
    def _avg_monthly_consumption(all_txns: list, mk: str) -> float:
        keys = [mk]
        for _ in range(2):
            keys.append(month_math.prev_month_key(keys[-1]))
        seen = [
            month_math.aggregate(month_math.in_month(all_txns, k)).consumption for k in keys
        ]
        active = [v for v in seen if v > 0]
        return sum(active) / len(active) if active else 0.0

    # -------------------------------------------------------------- snapshot
    def snapshot(self, household_id: int, mk: str) -> HealthSnapshot:
        """Persist the score for a month so improvement can be measured
        later. Re-running it for the same month overwrites the row — the
        month's final score is what matters, and the coin ledger (not this
        table) is the record of what was paid."""
        report = self.report(household_id, mk)
        row = self.snapshots.find(household_id, mk)
        if row is None:
            row = HealthSnapshot(household_id=household_id, month=mk, created_at=now_iso())
        else:
            row.updated_at = now_iso()
        row.score = report.score
        row.components = json.dumps(report.as_dict())
        return self.snapshots.save(row)

    def previous_score(self, household_id: int, mk: str) -> Optional[int]:
        row = self.snapshots.find(household_id, month_math.prev_month_key(mk))
        return row.score if row else None
