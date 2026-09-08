from typing import Optional

from app.schemas.base import CamelModel


class MemberIn(CamelModel):
    name: str
    relation: str = ""
    monthly_budget: float = 0


class MemberOut(CamelModel):
    id: int
    name: str
    relation: str
    monthly_budget: float
    created_at: str = ""
    updated_at: Optional[str] = None
