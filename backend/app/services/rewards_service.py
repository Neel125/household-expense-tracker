"""The reward engine.

It does three jobs and keeps them apart:

- **React to events.** Handlers subscribed to the domain event bus turn
  "an expense was tracked" into a coin, and "an expense was deleted" into
  a reversal. They never validate or persist anything themselves — the
  ledger owns that.
- **Settle periods.** Budget kept, saved more than last month, emergency
  fund on target, a subscription dropped, health improved, a challenge
  finished: none of these are a single user action, so they are evaluated
  in one idempotent sweep. `settle` runs lazily on read, which is the
  right trade for a self-hosted app with no scheduler; a production
  deployment would call the same method from a nightly job and the
  behaviour would be identical, because every award is keyed.
- **Report.** One summary the Rewards page can render whole.

`settle` only pays out for the last few complete months (SETTLE_MONTHS),
so switching the feature on doesn't hand a household with two years of
history a five-figure windfall — coins start accruing from now.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlmodel import Session

from app.models import CoinTransaction, Transaction
from app.repositories.repositories import (
    CategoryRepository,
    DebtRepository,
    GoalRepository,
    HouseholdRepo,
    IncomeSourceRepository,
    InvestmentRepository,
    TransactionRepository,
)
from app.services import month_math, reward_rules
from app.services.challenge_service import ChallengeService, ChallengeState
from app.services.coin_ledger import CoinLedger
from app.services.errors import NotFoundError, ValidationError
from app.services.events import (
    DEBT_COMPLETED,
    EXPENSE_DELETED,
    EXPENSE_TRACKED,
    GOAL_COMPLETED,
    INVESTMENT_ADDED,
    INVESTMENT_DELETED,
    INVESTMENT_MATURED,
    DomainEvent,
    subscribe,
)
from app.services.game_service import GameService, GameStatus
from app.services.health_service import HealthReport, HealthService
from app.services.portfolio_service import PortfolioService
from app.services.referral_service import ReferralService
from app.services.reward_rules import Level

# How far back a settle sweep will pay. Older months are still scored
# (for health-score baselines) but never awarded.
SETTLE_MONTHS = 3
# Coins per point of financial-health improvement, and the most one
# month's improvement can pay.
COINS_PER_HEALTH_POINT = 25
MAX_HEALTH_AWARD = 200
# A subscription counts as dropped only after this many months of
# consecutive charges followed by a month with none — enough history that
# a skipped bill isn't mistaken for a cancellation.
SUBSCRIPTION_HISTORY_MONTHS = 3


@dataclass(frozen=True)
class Streak:
    days: int
    best: int
    logged_today: bool


@dataclass(frozen=True)
class RewardsSummary:
    balance: int
    earned_this_month: int
    level: Level
    next_level: Optional[Level]
    streak: Streak
    health: HealthReport
    breakdown: dict[str, int]
    history: Sequence[CoinTransaction]
    challenges: list[ChallengeState]
    games: list[GameStatus]
    daily_cap_remaining: int
    review_month: str
    review_claimed: bool


class RewardsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.ledger = CoinLedger(session)
        self.challenges = ChallengeService(session)
        self.health = HealthService(session)
        self.transactions = TransactionRepository(session)
        self.households = HouseholdRepo(session)
        self.categories = CategoryRepository(session)
        self.income_sources = IncomeSourceRepository(session)
        self.goals = GoalRepository(session)
        self.investments = InvestmentRepository(session)
        self.debts = DebtRepository(session)
        self.portfolio = PortfolioService(session)
        self.referrals = ReferralService(session)
        self.games = GameService(session)

    # ------------------------------------------------------------- reactions
    def on_expense_tracked(self, event: DomainEvent) -> None:
        txn_id = event.payload.get("transaction_id")
        amount = float(event.payload.get("amount") or 0)
        if not txn_id or amount < reward_rules.MIN_REWARDABLE_AMOUNT:
            # A ₹0 row isn't tracking; refusing it closes the cheapest
            # possible farm loop.
            return
        if self._looks_automated(event.household_id):
            self.ledger.flag(
                event.household_id,
                # Minute precision, so sustained scripting leaves one row
                # a minute rather than one per blocked attempt.
                f"burst:{datetime.now(timezone.utc).isoformat()[:16]}",
                note=(
                    f"Over {reward_rules.BURST_MAX_EVENTS} entries in "
                    f"{reward_rules.BURST_WINDOW_SECONDS // 60} minutes — not rewarded"
                ),
                user_id=event.user_id,
            )
            return
        self.ledger.award(
            event.household_id,
            "EXPENSE_TRACKED",
            f"EXPENSE_TRACKED:txn:{txn_id}",
            user_id=event.user_id,
            reference_type="transaction",
            reference_id=str(txn_id),
            note=f"Logged “{event.payload.get('name') or 'expense'}”",
        )
        self._award_streak(event.household_id, event.user_id)

    def on_expense_deleted(self, event: DomainEvent) -> None:
        txn_id = event.payload.get("transaction_id")
        if not txn_id:
            return
        self.ledger.reverse(
            event.household_id,
            f"EXPENSE_TRACKED:txn:{txn_id}",
            kind="EXPENSE_REVERSED",
            note=f"Deleted “{event.payload.get('name') or 'expense'}”",
        )

    def on_goal_completed(self, event: DomainEvent) -> None:
        goal_id = event.payload.get("goal_id")
        if not goal_id:
            return
        self.ledger.award(
            event.household_id,
            "GOAL_COMPLETED",
            f"GOAL_COMPLETED:goal:{goal_id}",
            user_id=event.user_id,
            reference_type="goal",
            reference_id=str(goal_id),
            note=f"Completed “{event.payload.get('name') or 'goal'}”",
        )

    # ---------------------------------------------------- portfolio events
    def on_investment_added(self, event: DomainEvent) -> None:
        investment_id = event.payload.get("investment_id")
        if not investment_id:
            return
        name = event.payload.get("name") or "investment"
        self.ledger.award(
            event.household_id,
            "INVESTMENT_ADDED",
            f"INVESTMENT_ADDED:investment:{investment_id}",
            user_id=event.user_id,
            reference_type="investment",
            reference_id=str(investment_id),
            note=f"Tracked “{name}”",
        )

    def on_investment_deleted(self, event: DomainEvent) -> None:
        """Claw back both the tracking coin and any maturity payout when
        the underlying investment is removed. Reversal is a no-op if the
        original award never landed (cap hit, already reversed), so this
        is safe on every delete."""
        investment_id = event.payload.get("investment_id")
        if not investment_id:
            return
        name = event.payload.get("name") or "investment"
        self.ledger.reverse(
            event.household_id,
            f"INVESTMENT_ADDED:investment:{investment_id}",
            kind="INVESTMENT_REVERSED",
            note=f"Deleted “{name}”",
        )
        self.ledger.reverse(
            event.household_id,
            f"INVESTMENT_MATURED:investment:{investment_id}",
            kind="INVESTMENT_REVERSED",
            note=f"Deleted matured “{name}”",
        )

    def on_investment_matured(self, event: DomainEvent) -> None:
        investment_id = event.payload.get("investment_id")
        if not investment_id:
            return
        name = event.payload.get("name") or "investment"
        self.ledger.award(
            event.household_id,
            "INVESTMENT_MATURED",
            f"INVESTMENT_MATURED:investment:{investment_id}",
            user_id=event.user_id,
            reference_type="investment",
            reference_id=str(investment_id),
            note=f"“{name}” reached maturity",
        )

    def on_debt_completed(self, event: DomainEvent) -> None:
        """A loan just closed. The reward tier is chosen by the debt's
        kind — a home loan is worth ten times a consumer EMI — and the
        rule catalogue owns that mapping, not this handler."""
        debt_id = event.payload.get("debt_id")
        if not debt_id:
            return
        kind = event.payload.get("kind") or ""
        name = event.payload.get("name") or "loan"
        rule_key = reward_rules.loan_rule_for(kind)
        self.ledger.award(
            event.household_id,
            rule_key,
            # Kind is part of the key so a debt whose type is edited
            # after payoff doesn't get re-awarded under a new tier.
            f"{rule_key}:debt:{debt_id}",
            user_id=event.user_id,
            reference_type="debt",
            reference_id=str(debt_id),
            note=f"Paid off “{name}”",
        )

    def _looks_automated(self, household_id: int) -> bool:
        """Volume no hand can produce. The daily cap already limits what a
        farm loop earns; this stops it earning anything at all, and leaves
        a flagged row behind to look at."""
        since = (
            datetime.now(timezone.utc) - timedelta(seconds=reward_rules.BURST_WINDOW_SECONDS)
        ).isoformat()
        recent = self.transactions.count_created_since(household_id, since)
        return recent > reward_rules.BURST_MAX_EVENTS

    # ------------------------------------------------------------- streaks
    def _award_streak(self, household_id: int, user_id: Optional[int]) -> None:
        streak = self.streak(household_id)
        # Paid once per completed week of the streak: at 7 days, 14, 21…
        if streak.days >= 7 and streak.days % 7 == 0:
            self.ledger.award(
                household_id,
                "TRACKING_STREAK_7",
                f"TRACKING_STREAK_7:{datetime.now(timezone.utc).date().isoformat()}",
                user_id=user_id,
                note=f"{streak.days}-day tracking streak",
            )

    def streak(self, household_id: int, today: Optional[date] = None) -> Streak:
        """Consecutive days on which something was actually logged.

        Keyed off `created_at`, not the transaction date: the habit being
        rewarded is opening the app and recording spending, and back-
        filling a month in one sitting is one day of tracking, not thirty.
        Because `created_at` is stamped in UTC, so is the day boundary —
        the challenge and health code works off user-entered dates
        instead and uses the local day.
        """
        day = today or datetime.now(timezone.utc).date()
        days = {t.created_at[:10] for t in self.transactions.list(household_id) if t.created_at}
        if not days:
            return Streak(0, 0, False)

        logged_today = day.isoformat() in days
        cursor = day if logged_today else day - timedelta(days=1)
        current = 0
        while cursor.isoformat() in days:
            current += 1
            cursor -= timedelta(days=1)

        best, run, previous = 0, 0, None
        for value in sorted(days):
            parsed = date.fromisoformat(value)
            run = run + 1 if previous and (parsed - previous).days == 1 else 1
            best = max(best, run)
            previous = parsed
        return Streak(days=current, best=best, logged_today=logged_today)

    # -------------------------------------------------------------- settling
    def settle(self, household_id: int, user_id: Optional[int] = None) -> None:
        """Bring the ledger up to date. Safe to call on every request:
        every award inside is keyed, so a second run pays nothing."""
        today = date.today()
        current_month = month_math.this_month_key(today)
        months = self._settle_months(current_month)
        if not months:
            return

        # Score one month earlier than the earliest payable month so the
        # first improvement comparison has a baseline; each payable month
        # then snapshots itself in _settle_month, oldest first, so the
        # next month's comparison always has the row it needs.
        self.health.snapshot(household_id, month_math.prev_month_key(months[0]))
        # Keep the live month's score fresh for the UI. It is never paid —
        # an unfinished month can still get worse.
        self.health.snapshot(household_id, current_month)

        household = self.households.get(household_id)
        if not household:
            raise NotFoundError("Household not found")
        all_txns = list(self.transactions.list(household_id))
        sources = list(self.income_sources.list(household_id))

        for mk in months:
            self._settle_month(household_id, user_id, mk, household, all_txns, sources)

        # Holding the emergency fund at target is a statement about
        # *now*, so it pays a stipend for the current month rather than
        # being back-dated onto a month when the fund may not have existed.
        self._settle_emergency_fund(household_id, user_id, current_month)
        # A dropped subscription, by contrast, is only visible in history:
        # billed for three months, then absent from the month just gone.
        self._settle_subscriptions(household_id, user_id, months[-1], all_txns)
        self._settle_challenges(household_id, user_id)
        # Portfolio coins are normally awarded on create/update. Settle
        # also pays any investments/closed loans that already existed
        # before those handlers were wired — same event keys, so a later
        # create never double-pays.
        self._settle_portfolio(household_id, user_id)
        self._settle_referrals(household_id, user_id)

    def _settle_referrals(self, household_id: int, user_id: Optional[int]) -> None:
        """Pay both sides of a referral, once it has qualified.

        Handled symmetrically — this household's own referrals *and* the
        one that brought it in — so whichever side opens the app first
        moves the row to `qualified`, and the other side's payout is
        waiting the next time they look. Both awards key on the referral
        id, so running from both sides pays each exactly once.
        """
        for referral, progress in self.referrals.made_by(household_id):
            if referral.status != "qualified" and progress.qualified:
                self.referrals.mark_qualified(referral)
            if referral.status != "qualified" and not progress.qualified:
                continue
            if not self._referral_within_cap(household_id, referral):
                continue
            self.ledger.award(
                household_id,
                "REFERRAL_QUALIFIED",
                f"REFERRAL_QUALIFIED:referral:{referral.id}",
                user_id=user_id,
                reference_type="referral",
                reference_id=str(referral.id),
                note=f"{referral.referred_name or 'A friend'} started tracking",
            )

        joined = self.referrals.joined_through(household_id)
        if not joined:
            return
        referral, progress = joined
        if referral.status != "qualified" and progress.qualified:
            self.referrals.mark_qualified(referral)
        if referral.status != "qualified" and not progress.qualified:
            return
        self.ledger.award(
            household_id,
            "REFERRAL_WELCOME",
            f"REFERRAL_WELCOME:referral:{referral.id}",
            user_id=user_id,
            reference_type="referral",
            reference_id=str(referral.id),
            note=f"Joined through {self.referrals.referrer_name(referral) or 'a referral'}",
        )

    def _referral_within_cap(self, household_id: int, referral) -> bool:
        """A ceiling on referral payouts per calendar month.

        Qualification already costs an abuser days of pretending to be a
        household per fake account; this bounds the damage if someone has
        that patience anyway. A referral already paid is never re-counted,
        so an existing payout can't be pushed over the line by later ones.
        """
        key = f"REFERRAL_QUALIFIED:referral:{referral.id}"
        if self.ledger.already_awarded(household_id, key):
            return True
        month_start = f"{month_math.this_month_key()}-01T00:00:00+00:00"
        paid_this_month = self.ledger.coins.count_for_kind_since(
            household_id, "REFERRAL_QUALIFIED", month_start
        )
        if paid_this_month < reward_rules.REFERRAL_MONTHLY_CAP:
            return True
        self.ledger.flag(
            household_id,
            f"referral-cap:{month_math.this_month_key()}",
            note=(
                f"Monthly limit of {reward_rules.REFERRAL_MONTHLY_CAP} referral payouts "
                "reached — later referrals this month are not rewarded"
            ),
            user_id=None,
        )
        return False

    @staticmethod
    def _settle_months(current_month: str) -> list[str]:
        """The complete months eligible for payout, oldest first."""
        months: list[str] = []
        mk = month_math.prev_month_key(current_month)
        for _ in range(SETTLE_MONTHS):
            months.append(mk)
            mk = month_math.prev_month_key(mk)
        return list(reversed(months))

    def _settle_month(
        self,
        household_id: int,
        user_id: Optional[int],
        mk: str,
        household,
        all_txns: Sequence[Transaction],
        sources: Sequence,
    ) -> None:
        totals = month_math.aggregate(month_math.in_month(all_txns, mk))
        budget = household.monthly_budget or 0

        # Stayed within the monthly budget. A month with nothing logged
        # isn't discipline, so it needs real spend to count.
        if budget > 0 and 0 < totals.spend <= budget:
            self.ledger.award(
                household_id,
                "BUDGET_KEPT",
                f"BUDGET_KEPT:{mk}",
                user_id=user_id,
                reference_type="month",
                reference_id=mk,
                note=f"Stayed within budget in {mk}",
            )

        # Saved more than the month before.
        prev_key = month_math.prev_month_key(mk)
        prev_totals = month_math.aggregate(month_math.in_month(all_txns, prev_key))
        saved = month_math.monthly_income(totals, sources) - totals.consumption
        prev_saved = month_math.monthly_income(prev_totals, sources) - prev_totals.consumption
        if saved > 0 and saved > prev_saved:
            self.ledger.award(
                household_id,
                "SAVINGS_IMPROVED",
                f"SAVINGS_IMPROVED:{mk}",
                user_id=user_id,
                reference_type="month",
                reference_id=mk,
                note=f"Saved ₹{round(saved - prev_saved):,} more than {prev_key}",
            )

        # Improvement in the health score — the point of the score. The
        # payout scales with the gain, not with how rich the household is.
        score_now = self.health.snapshot(household_id, mk).score
        score_before = self.health.previous_score(household_id, mk)
        if score_before is not None and score_now > score_before:
            gain = score_now - score_before
            self.ledger.award(
                household_id,
                "HEALTH_SCORE_IMPROVED",
                f"HEALTH_SCORE_IMPROVED:{mk}",
                user_id=user_id,
                coins=min(MAX_HEALTH_AWARD, gain * COINS_PER_HEALTH_POINT),
                reference_type="month",
                reference_id=mk,
                note=f"Financial health {score_before} → {score_now}",
            )

    def _settle_emergency_fund(
        self, household_id: int, user_id: Optional[int], mk: str
    ) -> None:
        funds = [g for g in self.goals.list(household_id) if g.kind == "emergency"]
        target = sum(g.target_amount or 0 for g in funds)
        saved = sum(g.saved_amount or 0 for g in funds)
        if target > 0 and saved >= target:
            self.ledger.award(
                household_id,
                "EMERGENCY_FUND_ON_TARGET",
                f"EMERGENCY_FUND_ON_TARGET:{mk}",
                user_id=user_id,
                reference_type="month",
                reference_id=mk,
                note="Emergency fund held at target",
            )

    def _settle_subscriptions(
        self,
        household_id: int,
        user_id: Optional[int],
        mk: str,
        all_txns: Sequence[Transaction],
    ) -> None:
        """Reward a subscription that stopped being charged.

        Inferred rather than self-reported: a merchant in the
        Subscriptions category billed in each of the three months before
        `mk` and absent in `mk` has been cancelled.
        """
        ids = month_math.category_ids_named(
            self.categories.list(household_id), reward_rules.SUBSCRIPTION_CATEGORIES
        )
        if not ids:
            return

        def merchants(key: str) -> dict[str, str]:
            found: dict[str, str] = {}
            for t in month_math.in_month(all_txns, key):
                if t.type != "Expense" or t.category_id not in ids:
                    continue
                name = (t.merchant or t.name or "").strip()
                if name:
                    found[name.casefold()] = name
            return found

        history: list[dict[str, str]] = []
        cursor = mk
        for _ in range(SUBSCRIPTION_HISTORY_MONTHS):
            cursor = month_math.prev_month_key(cursor)
            history.append(merchants(cursor))
        if not all(history):
            return

        recurring = set(history[0])
        for older in history[1:]:
            recurring &= set(older)
        for key in sorted(recurring - set(merchants(mk))):
            name = history[0][key]
            self.ledger.award(
                household_id,
                "SUBSCRIPTION_DROPPED",
                f"SUBSCRIPTION_DROPPED:{key}:{mk}",
                user_id=user_id,
                reference_type="merchant",
                reference_id=name,
                note=f"Stopped paying for {name}",
            )

    def _settle_challenges(self, household_id: int, user_id: Optional[int]) -> None:
        for enrollment, state in self.challenges.pending(household_id):
            if state.outcome.achieved:
                self.ledger.award(
                    household_id,
                    "CHALLENGE_COMPLETED",
                    f"CHALLENGE_COMPLETED:{enrollment.challenge_key}:{enrollment.period}",
                    user_id=enrollment.user_id or user_id,
                    coins=state.challenge.coins,
                    reference_type="challenge",
                    reference_id=enrollment.challenge_key,
                    note=f"Completed “{state.challenge.title}”",
                )
            self.challenges.mark_settled(
                enrollment, "completed" if state.outcome.achieved else "missed"
            )

    def _settle_portfolio(self, household_id: int, user_id: Optional[int]) -> None:
        """Pay for investments already on the books, and for loans already
        closed. Uses the same event keys as the live handlers so a later
        create/update never pays twice."""
        for inv in self.investments.list(household_id):
            self.ledger.award(
                household_id,
                "INVESTMENT_ADDED",
                f"INVESTMENT_ADDED:investment:{inv.id}",
                user_id=user_id,
                reference_type="investment",
                reference_id=str(inv.id),
                note=f"Tracked “{inv.name}”",
            )
            if self._investment_is_matured(inv):
                self.ledger.award(
                    household_id,
                    "INVESTMENT_MATURED",
                    f"INVESTMENT_MATURED:investment:{inv.id}",
                    user_id=user_id,
                    reference_type="investment",
                    reference_id=str(inv.id),
                    note=f"“{inv.name}” reached maturity",
                )
        # `Debt.outstanding` is only the balance tracking started from —
        # linked EMIs are what actually close a loan, so the portfolio
        # read model is the authority on which ones are paid off.
        for debt, view in self.portfolio.debt_views(household_id):
            if not view.is_closed:
                continue
            if float(debt.principal or 0) <= 0:
                continue
            kind = debt.kind or ""
            rule_key = reward_rules.loan_rule_for(kind)
            self.ledger.award(
                household_id,
                rule_key,
                f"{rule_key}:debt:{debt.id}",
                user_id=user_id,
                reference_type="debt",
                reference_id=str(debt.id),
                note=f"Paid off “{debt.name}”",
            )

    @staticmethod
    def _investment_is_matured(inv) -> bool:
        raw = (inv.maturity_date or "").strip()
        if not raw:
            return False
        try:
            return date.fromisoformat(raw[:10]) <= date.today()
        except ValueError:
            return False

    # ---------------------------------------------------------------- actions
    def record_review(self, household_id: int, user_id: Optional[int], month: str) -> int:
        """Pay for actually reading the month's numbers. Once per month,
        and only for a month that is over — there is nothing to review
        about a month still in progress."""
        if not month or len(month) != 7:
            raise ValidationError("Give the month to review as YYYY-MM")
        if not month_math.is_complete(month):
            raise ValidationError("That month isn't over yet")
        row = self.ledger.award(
            household_id,
            "MONTHLY_REVIEW",
            f"MONTHLY_REVIEW:{month}",
            user_id=user_id,
            reference_type="month",
            reference_id=month,
            note=f"Reviewed {month} spending",
        )
        return row.amount if row else 0

    # ---------------------------------------------------------------- reports
    def summary(self, household_id: int, user_id: Optional[int] = None) -> RewardsSummary:
        self.settle(household_id, user_id)

        balance = self.ledger.balance(household_id)
        breakdown = {k: v for k, v in self.ledger.totals_by_kind(household_id).items() if v}
        month_prefix = month_math.this_month_key()
        earned = sum(
            row.amount
            for row in self.ledger.history(household_id, limit=500)
            if row.created_at[:7] == month_prefix and row.amount > 0
        )
        expense_rule = reward_rules.RULES["EXPENSE_TRACKED"]
        earned_today = self.ledger.earned_today(household_id, "EXPENSE_TRACKED")
        review_month = month_math.prev_month_key(month_prefix)

        return RewardsSummary(
            balance=balance,
            earned_this_month=earned,
            level=reward_rules.level_for(balance),
            next_level=reward_rules.next_level(balance),
            streak=self.streak(household_id),
            health=self.health.report(household_id),
            breakdown=breakdown,
            history=self.ledger.history(household_id, limit=40),
            challenges=self.challenges.states(household_id),
            games=self.games.statuses(household_id),
            daily_cap_remaining=max(0, (expense_rule.daily_cap or 0) - earned_today),
            review_month=review_month,
            review_claimed=self.ledger.already_awarded(
                household_id, f"MONTHLY_REVIEW:{review_month}"
            ),
        )


# ------------------------------------------------------------------- wiring
def register_handlers() -> None:
    """Connect the engine to the event bus. Called once from
    app.main:create_app so no service has to import RewardsService."""

    def handler(name: str):
        def dispatch(session: Session, event: DomainEvent) -> None:
            service = RewardsService(session)
            getattr(service, name)(event)

        return dispatch

    subscribe(EXPENSE_TRACKED, handler("on_expense_tracked"))
    subscribe(EXPENSE_DELETED, handler("on_expense_deleted"))
    subscribe(GOAL_COMPLETED, handler("on_goal_completed"))
    subscribe(INVESTMENT_ADDED, handler("on_investment_added"))
    subscribe(INVESTMENT_DELETED, handler("on_investment_deleted"))
    subscribe(INVESTMENT_MATURED, handler("on_investment_matured"))
    subscribe(DEBT_COMPLETED, handler("on_debt_completed"))
