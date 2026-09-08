from typing import Optional

from app.schemas.base import CamelModel


class GoalIn(CamelModel):
    name: str
    kind: str = "custom"
    target_amount: float = 0
    saved_amount: float = 0
    target_date: str = ""


class GoalContributionIn(CamelModel):
    amount: float


class GoalOut(CamelModel):
    id: int
    name: str
    kind: str
    target_amount: float
    saved_amount: float
    target_date: str
    created_at: str = ""
    updated_at: Optional[str] = None
