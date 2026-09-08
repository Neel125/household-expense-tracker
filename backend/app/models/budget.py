from typing import Optional

from sqlmodel import Field, SQLModel


class CategoryBudget(SQLModel, table=True):
    """What share of the household's monthly budget a category should get.
    Stored as a percentage; the rupee amount is derived
    (Household.monthly_budget * percentage / 100)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    category_id: int = Field(index=True, foreign_key="category.id")
    percentage: float = 0  # 0..100
    created_at: str = ""
    updated_at: Optional[str] = None
