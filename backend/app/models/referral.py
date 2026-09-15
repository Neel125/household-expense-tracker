from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Referral(SQLModel, table=True):
    """One household brought in by another.

    This is deliberately *not* the same thing as an Invite. An invite adds
    a person to an existing household — they share the same books, so
    paying coins for one would be free money for typing in an email. A
    referral brings a whole new household into existence, and only pays
    once that household behaves like a real one (see
    reward_rules.REFERRAL_* and ReferralService.progress).

    `status` moves pending -> qualified once, and never back: the coin
    ledger keys its award on this row's id, so a row that flickered would
    still only ever be paid once.
    """

    __table_args__ = (
        # A household can only have been referred by someone once — it is
        # created at the moment it is referred, so there is no second
        # chance to claim it.
        UniqueConstraint("referred_household_id", name="uq_referral_referred"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True)  # the code that was used, kept for audit
    referrer_household_id: int = Field(index=True, foreign_key="household.id")
    referred_household_id: int = Field(index=True, foreign_key="household.id")
    referred_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # Display name only. The referrer never sees the email address of the
    # person who signed up — they already know who they sent the link to,
    # and the address is not theirs to have.
    referred_name: str = ""
    status: str = "pending"  # pending | qualified
    created_at: str = ""
    qualified_at: Optional[str] = None
