"""Short-term financial challenges.

Definitions live in reward_rules.CHALLENGES; only the fact that a
household joined one is stored (ChallengeEnrollment). Progress is
recomputed from transactions on every read, which means a challenge can
never drift out of sync with the books — editing or deleting a
transaction re-scores it immediately.

A challenge is only *settled* (paid) once its window has closed, so no
challenge can be claimed while it could still be failed: "no shopping for
seven days" pays on day seven, not on day one at 0 spend.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Optional, Sequence

from sqlmodel import Session

from app.models import Category, ChallengeEnrollment, Transaction
from app.models.mixins import now_iso
from app.repositories.repositories import (
    ChallengeEnrollmentRepository,
    CategoryRepository,
    HouseholdRepo,
    IncomeSourceRepository,
    TransactionRepository,
)
from app.services import month_math, reward_rules
from app.services.errors import NotFoundError, ValidationError
from app.services.reward_rules import CHALLENGES, CHALLENGES_BY_KEY, Challenge


@dataclass
class Context:
    """Everything an evaluator may look at.

    `reference` is any day inside the challenge's own period and `today`
    is the real date — keeping them separate is what lets a challenge
    from last week be scored correctly when it is settled this week.
    """

    today: date
    reference: date
    all_txns: Sequence[Transaction]
    categories: Sequence[Category]
    income_sources: Sequence
    period: str
    joined_on: Optional[date]


@dataclass(frozen=True)
class Outcome:
    """How one challenge stands: `current`/`target` drive the progress
    bar, `achieved` says it was met, `window_over` says it can no longer
    change."""

    current: float
    target: float
    caption: str
    achieved: bool
    window_over: bool
    eligible: bool = True  # False when the challenge can't be scored yet

    @property
    def pct(self) -> int:
        if self.target <= 0:
            return 100 if self.achieved else 0
        return int(max(0, min(100, round(self.current / self.target * 100))))


@dataclass(frozen=True)
class ChallengeState:
    challenge: Challenge
    period: str
    status: str  # available | active | completed | missed
    outcome: Outcome


def _week_key(day: date) -> str:
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def _week_bounds(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _period_reference(challenge: Challenge, period: str) -> date:
    """A day inside `period` — the Monday of a week key, the 1st of a
    month key. Falls back to today if the key is malformed."""
    try:
        if challenge.period == "week":
            year, week = int(period[:4]), int(period[6:])
            return date.fromisocalendar(year, week, 1)
        return date(int(period[:4]), int(period[5:7]), 1)
    except ValueError:
        return date.today()


def _txn_dates(txns: Sequence[Transaction]) -> set[date]:
    out = set()
    for t in txns:
        try:
            out.add(date.fromisoformat(t.date))
        except (TypeError, ValueError):
            continue
    return out


def _between(txns: Sequence[Transaction], start: date, end: date) -> list[Transaction]:
    lo, hi = start.isoformat(), end.isoformat()
    return [t for t in txns if t.date and lo <= t.date <= hi]


# --------------------------------------------------------------- evaluators
def _no_spend_weekend(ctx: Context) -> Outcome:
    monday, _ = _week_bounds(ctx.reference)
    weekend = [monday + timedelta(days=5), monday + timedelta(days=6)]
    elapsed = [d for d in weekend if d < ctx.today]
    clear = 0
    for day in elapsed:
        wants = [
            t
            for t in _between(ctx.all_txns, day, day)
            if t.necessity == "Want" and t.type not in {"Income", "CC Repayment"}
        ]
        if not wants:
            clear += 1
    window_over = ctx.today > weekend[1]
    if not elapsed:
        caption = "Starts Saturday"
    elif clear == len(elapsed):
        caption = f"{clear} of 2 weekend days clear"
    else:
        caption = "Discretionary spend logged this weekend"
    return Outcome(
        current=clear,
        target=2,
        caption=caption,
        achieved=window_over and clear == 2,
        window_over=window_over,
    )


def _no_shopping_7_days(ctx: Context) -> Outcome:
    start = ctx.joined_on or ctx.today
    ids = month_math.category_ids_named(ctx.categories, reward_rules.DISCRETIONARY_CATEGORIES)
    clear = 0
    for offset in range(7):
        day = start + timedelta(days=offset)
        if day >= ctx.today:  # today isn't over yet
            break
        spend = month_math.spend_in_categories(_between(ctx.all_txns, day, day), ids)
        if spend > 0:
            break
        clear += 1
    window_over = ctx.today > start + timedelta(days=6)
    return Outcome(
        current=clear,
        target=7,
        caption=f"{clear} of 7 days clear",
        achieved=clear >= 7,
        window_over=window_over,
        eligible=bool(ids),
    )


def _track_every_expense(ctx: Context) -> Outcome:
    total_days = month_math.days_in_month(ctx.period)
    month_txns = month_math.in_month(ctx.all_txns, ctx.period)
    tracked = len(_txn_dates(month_txns))
    window_over = month_math.is_complete(ctx.period, ctx.today)
    return Outcome(
        current=tracked,
        target=total_days,
        caption=f"{tracked} of {total_days} days tracked",
        achieved=tracked >= total_days,
        window_over=window_over,
    )


def _save_5000(ctx: Context) -> Outcome:
    target = 5000.0
    totals = month_math.aggregate(month_math.in_month(ctx.all_txns, ctx.period))
    income = month_math.monthly_income(totals, ctx.income_sources)
    saved = income - totals.consumption
    window_over = month_math.is_complete(ctx.period, ctx.today)
    return Outcome(
        current=max(0.0, saved),
        target=target,
        caption=f"₹{round(max(0.0, saved)):,} of ₹{round(target):,} saved",
        achieved=saved >= target,
        window_over=window_over,
    )


def _cut_eating_out(ctx: Context) -> Outcome:
    ids = month_math.category_ids_named(ctx.categories, reward_rules.EATING_OUT_CATEGORIES)
    prev_key = month_math.prev_month_key(ctx.period)
    baseline = month_math.spend_in_categories(month_math.in_month(ctx.all_txns, prev_key), ids)
    spend = month_math.spend_in_categories(month_math.in_month(ctx.all_txns, ctx.period), ids)
    window_over = month_math.is_complete(ctx.period, ctx.today)
    if baseline <= 0:
        return Outcome(
            current=0,
            target=1,
            caption="No eating-out spend last month to improve on",
            achieved=False,
            window_over=window_over,
            eligible=False,
        )
    ceiling = baseline * 0.8
    cut = baseline - spend
    needed = baseline - ceiling
    return Outcome(
        current=max(0.0, cut),
        target=needed,
        caption=f"₹{round(spend):,} spent, ₹{round(ceiling):,} allowed",
        achieved=spend <= ceiling,
        window_over=window_over,
    )


EVALUATORS: dict[str, Callable[[Context], Outcome]] = {
    "no_spend_weekend": _no_spend_weekend,
    "no_shopping_7_days": _no_shopping_7_days,
    "track_every_expense": _track_every_expense,
    "save_5000": _save_5000,
    "cut_eating_out": _cut_eating_out,
}


class ChallengeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.enrollments = ChallengeEnrollmentRepository(session)
        self.transactions = TransactionRepository(session)
        self.categories = CategoryRepository(session)
        self.income_sources = IncomeSourceRepository(session)
        self.households = HouseholdRepo(session)

    @staticmethod
    def period_for(challenge: Challenge, today: Optional[date] = None) -> str:
        day = today or date.today()
        return _week_key(day) if challenge.period == "week" else month_math.this_month_key(day)

    def states(self, household_id: int, today: Optional[date] = None) -> list[ChallengeState]:
        """Every challenge with this household's live progress, for the
        period each one is currently in."""
        day = today or date.today()
        data = self._load(household_id)
        return [
            self._evaluate(household_id, c, self.period_for(c, day), day, data)
            for c in CHALLENGES
        ]

    def pending(
        self, household_id: int, today: Optional[date] = None
    ) -> list[tuple[ChallengeEnrollment, ChallengeState]]:
        """Joined challenges whose window has closed and that have not
        been settled yet — what RewardsService.settle pays out on. Past
        periods are included, so a household that was away for a week
        still gets last week's challenge resolved."""
        day = today or date.today()
        data = self._load(household_id)
        out = []
        for enrollment in self.enrollments.list(household_id):
            if enrollment.status != "active" or enrollment.settled_at:
                continue
            challenge = CHALLENGES_BY_KEY.get(enrollment.challenge_key)
            if challenge is None:  # a challenge that has since been retired
                continue
            state = self._evaluate(household_id, challenge, enrollment.period, day, data)
            if state.outcome.window_over:
                out.append((enrollment, state))
        return out

    def _load(self, household_id: int) -> dict:
        return {
            "all_txns": list(self.transactions.list(household_id)),
            "categories": list(self.categories.list(household_id)),
            "income_sources": list(self.income_sources.list(household_id)),
        }

    def _evaluate(
        self,
        household_id: int,
        challenge: Challenge,
        period: str,
        today: date,
        data: dict,
    ) -> ChallengeState:
        enrollment = self.enrollments.find(household_id, challenge.key, period)
        joined_on = None
        if enrollment and enrollment.joined_at:
            try:
                joined_on = date.fromisoformat(enrollment.joined_at[:10])
            except ValueError:
                joined_on = None
        outcome = EVALUATORS[challenge.key](
            Context(
                today=today,
                reference=_period_reference(challenge, period),
                all_txns=data["all_txns"],
                categories=data["categories"],
                income_sources=data["income_sources"],
                period=period,
                joined_on=joined_on,
            )
        )
        return ChallengeState(
            challenge=challenge,
            period=period,
            status=self._status(enrollment, outcome),
            outcome=outcome,
        )

    @staticmethod
    def _status(enrollment: Optional[ChallengeEnrollment], outcome: Outcome) -> str:
        if enrollment is None:
            return "available"
        if enrollment.status != "active":
            return enrollment.status
        if outcome.window_over:
            return "completed" if outcome.achieved else "missed"
        return "active"

    def join(self, household_id: int, user_id: Optional[int], challenge_key: str) -> ChallengeState:
        challenge = CHALLENGES_BY_KEY.get(challenge_key)
        if not challenge:
            raise NotFoundError("Challenge not found")
        period = self.period_for(challenge)
        if self.enrollments.find(household_id, challenge_key, period) is None:
            self.enrollments.add(
                ChallengeEnrollment(
                    household_id=household_id,
                    user_id=user_id,
                    challenge_key=challenge_key,
                    period=period,
                    status="active",
                    joined_at=now_iso(),
                )
            )
        state = next(
            (s for s in self.states(household_id) if s.challenge.key == challenge_key),
            None,
        )
        if state is None:  # unreachable — the key was validated above
            raise ValidationError("Challenge could not be started")
        return state

    def leave(self, household_id: int, challenge_key: str) -> None:
        challenge = CHALLENGES_BY_KEY.get(challenge_key)
        if not challenge:
            raise NotFoundError("Challenge not found")
        enrollment = self.enrollments.find(household_id, challenge_key, self.period_for(challenge))
        if enrollment is None:
            raise NotFoundError("You haven't joined that challenge")
        if enrollment.settled_at:
            raise ValidationError("That challenge has already been settled")
        self.enrollments.delete(enrollment)

    def mark_settled(self, enrollment: ChallengeEnrollment, status: str) -> None:
        enrollment.status = status
        enrollment.settled_at = now_iso()
        self.enrollments.save(enrollment)

    def enrollment(
        self, household_id: int, challenge_key: str, period: str
    ) -> Optional[ChallengeEnrollment]:
        return self.enrollments.find(household_id, challenge_key, period)
