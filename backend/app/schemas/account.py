from typing import Optional

from app.schemas.base import CamelModel


class AccountIn(CamelModel):
    name: str
    type: str = "bank"
    institution: str = ""
    opening_balance: float = 0
    linked_account_id: Optional[int] = None
    archived: bool = False


class AccountOut(CamelModel):
    id: int
    name: str
    type: str
    institution: str
    opening_balance: float
    linked_account_id: Optional[int] = None
    archived: bool
    created_at: str = ""
    updated_at: Optional[str] = None
