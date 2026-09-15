from typing import Optional

from sqlmodel import Field, SQLModel


class Household(SQLModel, table=True):
    """A family's shared books. Every financial row is scoped to one of
    these via household_id — this is the tenancy boundary."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    # The total monthly spending envelope; category budgets are a
    # percentage of this. 0 = not set yet.
    monthly_budget: float = 0
    # Shareable "refer a friend" code, e.g. "LC-7KQ2M4". Generated on
    # first use rather than at signup, so households that never open the
    # Rewards page never get one.
    referral_code: str = Field(default="", index=True)
    created_at: str = ""
    updated_at: Optional[str] = None
