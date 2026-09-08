from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class CoinTransaction(SQLModel, table=True):
    """One immutable line in the coin ledger.

    The balance is never stored — it is SUM(amount) over these rows, so
    every coin a household holds can be traced to the behaviour that
    earned it. Rows are append-only: a mistake is corrected by writing a
    compensating row (see CoinLedger.reverse), never by editing history.

    Coins are held by the *household* (the app's tenancy boundary — the
    family shares one set of books, so it shares one purse); `user_id`
    records which login earned the row, for attribution only.
    """

    __table_args__ = (
        # Idempotency: a given real-world event can only ever be paid
        # once. `event_key` encodes the rule and the thing it refers to
        # (e.g. "EXPENSE_TRACKED:txn:412", "BUDGET_KEPT:2026-08").
        UniqueConstraint("household_id", "event_key", name="uq_coin_event"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    kind: str = Field(index=True)  # a rule key from services.reward_rules
    # Signed, in whole coins: credits are positive, reversals and (future)
    # redemptions negative. A zero-amount row records something worth
    # auditing that paid nothing — a capped or flagged award.
    amount: int = 0
    event_key: str = Field(index=True)
    reference_type: str = ""  # transaction | goal | challenge | month | merchant
    reference_id: str = ""
    note: str = ""  # human-readable, shown in the coin history
    created_at: str = Field(default="", index=True)


class ChallengeEnrollment(SQLModel, table=True):
    """A household opting into one challenge for one period.

    Challenge *definitions* live in code (services.reward_rules) and
    progress is recomputed from transactions on every read, so this table
    only stores the parts that can't be derived: that they joined, and
    whether it has been settled.
    """

    __table_args__ = (
        UniqueConstraint("household_id", "challenge_key", "period", name="uq_challenge_period"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    challenge_key: str = Field(index=True)
    period: str = ""  # "2026-09" for monthly, "2026-W37" for weekly
    status: str = "active"  # active | completed | missed
    joined_at: str = ""
    settled_at: Optional[str] = None


class HealthSnapshot(SQLModel, table=True):
    """The financial-health score as it stood at the end of a month.

    Kept so improvement can be rewarded rather than absolute wealth: the
    engine compares this month's score with the previous month's row.
    """

    __table_args__ = (UniqueConstraint("household_id", "month", name="uq_health_month"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    month: str = Field(index=True)  # "YYYY-MM"
    score: int = 0  # 0..100
    components: str = ""  # JSON: {"budget": 90, "savings": 78, ...}
    created_at: str = ""
    updated_at: Optional[str] = None
