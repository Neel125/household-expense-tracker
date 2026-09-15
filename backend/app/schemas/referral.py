"""Referral DTOs.

The referrer's list carries display names and progress, never email
addresses: they already know who they sent the link to, and the address
is not theirs to have.
"""
from typing import Optional

from app.schemas.base import CamelModel


class ReferralRowOut(CamelModel):
    id: int
    name: str
    status: str  # pending | qualified
    # How far the referred household is toward earning both sides a payout.
    expenses: int
    active_days: int
    needed_expenses: int
    needed_days: int
    pct: int
    created_at: str
    qualified_at: Optional[str] = None

    @classmethod
    def of(cls, referral, progress) -> "ReferralRowOut":
        return cls(
            id=referral.id,
            name=referral.referred_name or "A friend",
            status=referral.status,
            expenses=progress.expenses,
            active_days=progress.active_days,
            needed_expenses=progress.needed_expenses,
            needed_days=progress.needed_days,
            pct=progress.pct,
            created_at=referral.created_at,
            qualified_at=referral.qualified_at,
        )


class JoinedThroughOut(CamelModel):
    """The referral that brought *this* household in, from its own side."""

    referrer_name: str
    status: str
    pct: int
    expenses: int
    active_days: int
    needed_expenses: int
    needed_days: int
    welcome_coins: int


class ReferralSummaryOut(CamelModel):
    code: str
    # Path only. The backend has no idea what public origin the app is
    # served from, so the client joins this to its own origin.
    share_path: str
    reward_coins: int
    welcome_coins: int
    needed_expenses: int
    needed_days: int
    monthly_cap: int
    qualified_count: int
    pending_count: int
    coins_earned: int
    referrals: list[ReferralRowOut]
    joined_through: Optional[JoinedThroughOut] = None


class ReferralPreviewOut(CamelModel):
    """What the sign-up screen shows for a code in the URL.

    Carries the thresholds as well as the name so the sign-up copy is
    generated from the rules rather than repeating them — change
    REFERRAL_MIN_* and both screens follow.
    """

    valid: bool
    household_name: str = ""
    welcome_coins: int = 0
    needed_expenses: int = 0
    needed_days: int = 0
