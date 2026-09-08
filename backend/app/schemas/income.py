from typing import Optional

from app.schemas.base import CamelModel


class IncomeSourceIn(CamelModel):
    name: str
    kind: str = "salary"
    monthly_amount: float = 0
    member: str = ""
    active: bool = True


class IncomeSourceOut(CamelModel):
    id: int
    name: str
    kind: str
    monthly_amount: float
    member: str
    active: bool
    created_at: str = ""
    updated_at: Optional[str] = None
