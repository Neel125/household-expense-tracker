from typing import Optional

from sqlmodel import Field, SQLModel


class Goal(SQLModel, table=True):
    """A savings target: emergency fund, vacation, education, etc. It is a
    tracker — contributions are recorded manually and do not move account
    balances automatically."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str
    kind: str = "custom"  # emergency | vacation | education | home | vehicle | custom
    target_amount: float = 0
    saved_amount: float = 0
    target_date: str = ""  # "YYYY-MM-DD", optional
    created_at: str = ""
    updated_at: Optional[str] = None
