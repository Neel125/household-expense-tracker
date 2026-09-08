from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    """A login. Belongs to exactly one household. The owner (the person
    who registered) can invite others and manage accounts/budget; members
    share the same books."""

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    password_hash: str
    display_name: str = ""
    contact_number: str = ""
    # Small profile image, stored as a base64 data URI so we don't need an
    # object store for a single-tenant self-hosted app. Empty means "use the
    # initials avatar".
    avatar_url: str = ""
    household_id: int = Field(index=True, foreign_key="household.id")
    role: str = "member"  # owner | member
    # The family member this login logs transactions as (Transaction.member
    # stores the name). Optional so a login can exist before it is linked.
    member_id: Optional[int] = Field(default=None, foreign_key="member.id")
    created_at: str = ""
    updated_at: Optional[str] = None
