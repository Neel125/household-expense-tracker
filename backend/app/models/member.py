from typing import Optional

from sqlmodel import Field, SQLModel


class Member(SQLModel, table=True):
    """A person in the household. Transactions reference a member by
    *name* (Transaction.member), so a rename cascades — see
    MemberService."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str = Field(index=True)
    relation: str = ""  # Self | Spouse | Parent | Child | Sibling | Other
    monthly_budget: float = 0  # personal cap; 0 = none
    created_at: str = ""
    updated_at: Optional[str] = None
