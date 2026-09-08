from typing import Optional

from sqlmodel import Field, SQLModel


class Category(SQLModel, table=True):
    """A spending category. Each household is seeded with a predefined
    set on creation; users add custom ones."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str
    color: str = ""  # hex or CSS var, for charts
    is_custom: bool = False
    archived: bool = False
    sort_order: int = 0
    created_at: str = ""
    updated_at: Optional[str] = None
