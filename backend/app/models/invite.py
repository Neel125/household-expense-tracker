from typing import Optional

from sqlmodel import Field, SQLModel


class Invite(SQLModel, table=True):
    """A single-use link that lets someone join an existing household.
    The owner shares the token; there is no email delivery built in."""

    id: Optional[int] = Field(default=None, primary_key=True)
    token: str = Field(index=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    email: str = ""  # optional hint of who it's for
    relation: str = ""  # suggested relation for the member they'll become
    invited_by: str = ""
    expires_at: str = ""
    accepted_at: Optional[str] = None
    created_at: str = ""
