from typing import Optional

from sqlmodel import Field, SQLModel


class IncomeSource(SQLModel, table=True):
    """A recurring monthly income line — salary or other. One-off income
    is logged as a Transaction of type 'Income' instead."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str
    kind: str = "salary"  # salary | other
    monthly_amount: float = 0
    member: str = ""  # whose income (member name), optional
    active: bool = True
    created_at: str = ""
    updated_at: Optional[str] = None
