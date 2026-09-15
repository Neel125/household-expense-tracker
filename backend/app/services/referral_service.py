"""Refer a friend.

The distinction that makes this safe: an **invite** adds a person to an
existing household, and a **referral** brings a whole new household into
existence. Paying for invites would be free money — the "members" share
your books, so ten throwaway addresses would mint ten payouts for typing
in ten emails. That is why referrals were left out when the reward
catalogue was first built.

What makes them payable now is *qualification*. A referral sits at
`pending` and earns nothing until the referred household behaves like a
real one: enough expenses logged, spread over enough separate days
(counted from when rows were actually entered, so back-filling an evening
doesn't count as a week). Only then does either side see a coin.

This service owns the code, the link between the two households, and the
qualification test. It never writes to the ledger — RewardsService does
that, so every coin in the app is still awarded in exactly one place.
"""
import secrets
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlmodel import Session

from app.models import Household, Referral, Transaction
from app.models.mixins import now_iso
from app.repositories.repositories import (
    HouseholdRepo,
    ReferralRepository,
    TransactionRepository,
)
from app.services import reward_rules
from app.services.errors import NotFoundError, ValidationError

# Only day-to-day spending counts toward qualification — the same row type
# the tracking habit is built on.
_QUALIFYING_TYPE = "Expense"


@dataclass(frozen=True)
class Progress:
    """How close a referred household is to earning both sides a payout."""

    expenses: int
    active_days: int
    needed_expenses: int
    needed_days: int

    @property
    def qualified(self) -> bool:
        return self.expenses >= self.needed_expenses and self.active_days >= self.needed_days

    @property
    def pct(self) -> int:
        """A single number for a progress bar: the weaker of the two
        requirements, so the bar never reads 90% when one half is at zero."""
        a = min(1.0, self.expenses / self.needed_expenses) if self.needed_expenses else 1.0
        b = min(1.0, self.active_days / self.needed_days) if self.needed_days else 1.0
        return int(round(min(a, b) * 100))


class ReferralService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.referrals = ReferralRepository(session)
        self.households = HouseholdRepo(session)
        self.transactions = TransactionRepository(session)

    # ------------------------------------------------------------- the code
    def code_for(self, household_id: int) -> str:
        """This household's share code, generated on first ask.

        Lazily rather than at signup: a household that never opens the
        Rewards page never needs one, and generating on demand keeps the
        collision retry in one place.
        """
        household = self.households.get(household_id)
        if not household:
            raise NotFoundError("Household not found")
        if household.referral_code:
            return household.referral_code
        household.referral_code = self._mint_code()
        household.updated_at = now_iso()
        self.households.save(household)
        return household.referral_code

    def _mint_code(self) -> str:
        alphabet = reward_rules.REFERRAL_CODE_ALPHABET
        for _ in range(12):
            body = "".join(secrets.choice(alphabet) for _ in range(reward_rules.REFERRAL_CODE_LENGTH))
            code = reward_rules.REFERRAL_CODE_PREFIX + body
            if not self.households.find_by_referral_code(code):
                return code
        # 32^6 is about a billion codes; a dozen collisions in a row means
        # something is wrong rather than unlucky.
        raise ValidationError("Could not generate a referral code, please try again")

    def preview(self, code: str) -> Optional[Household]:
        """Who a code belongs to, for the sign-up screen. Returns None for
        anything unrecognised — a bad code must never block a signup, it
        just doesn't earn anything."""
        return self.households.find_by_referral_code(code)

    # -------------------------------------------------------------- linking
    def attach(
        self,
        code: str,
        referred_household_id: int,
        referred_user_id: Optional[int],
        referred_name: str,
    ) -> Optional[Referral]:
        """Record that a brand-new household arrived through a code.

        Returns None whenever the referral simply doesn't apply — an
        unknown code, or a household somehow referring itself. Signing up
        is never blocked by a referral problem; the account is the point,
        the coins are a bonus.
        """
        referrer = self.households.find_by_referral_code(code)
        if not referrer or referrer.id == referred_household_id:
            return None
        if self.referrals.for_referred(referred_household_id):
            return None  # already attributed; a household is referred once
        return self.referrals.add(
            Referral(
                code=referrer.referral_code,
                referrer_household_id=referrer.id,
                referred_household_id=referred_household_id,
                referred_user_id=referred_user_id,
                referred_name=(referred_name or "").strip(),
                status="pending",
                created_at=now_iso(),
            )
        )

    # -------------------------------------------------------- qualification
    def progress(self, referral: Referral) -> Progress:
        """Measure the referred household against the thresholds.

        Active days come from `created_at` — the day a row was *entered* —
        so ten expenses typed in one sitting is one day of activity, not
        ten. That is the part an abuser cannot shortcut.
        """
        rows: Sequence[Transaction] = self.transactions.list(referral.referred_household_id)
        expenses = [t for t in rows if t.type == _QUALIFYING_TYPE and (t.amount or 0) > 0]
        days = {t.created_at[:10] for t in expenses if t.created_at}
        return Progress(
            expenses=len(expenses),
            active_days=len(days),
            needed_expenses=reward_rules.REFERRAL_MIN_EXPENSES,
            needed_days=reward_rules.REFERRAL_MIN_ACTIVE_DAYS,
        )

    def mark_qualified(self, referral: Referral) -> Referral:
        if referral.status == "qualified":
            return referral
        referral.status = "qualified"
        referral.qualified_at = now_iso()
        return self.referrals.save(referral)

    # ---------------------------------------------------------------- reads
    def made_by(self, household_id: int) -> list[tuple[Referral, Progress]]:
        return [(r, self.progress(r)) for r in self.referrals.made_by(household_id)]

    def joined_through(self, household_id: int) -> Optional[tuple[Referral, Progress]]:
        referral = self.referrals.for_referred(household_id)
        return (referral, self.progress(referral)) if referral else None

    def referrer_name(self, referral: Referral) -> str:
        household = self.households.get(referral.referrer_household_id)
        return household.name if household else ""
