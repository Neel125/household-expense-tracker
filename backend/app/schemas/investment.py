from typing import Optional

from app.schemas.base import CamelModel


class InvestmentIn(CamelModel):
    name: str
    kind: str = "other"
    institution: str = ""
    amount_invested: float = 0
    current_value: float = 0
    annual_return_pct: float = 0
    monthly_contribution: float = 0
    start_date: str = ""
    maturity_date: str = ""
    notes: str = ""


class InvestmentOut(CamelModel):
    id: int
    name: str
    kind: str
    institution: str
    amount_invested: float
    current_value: float
    annual_return_pct: float
    monthly_contribution: float
    start_date: str
    maturity_date: str
    notes: str
    created_at: str = ""
    updated_at: Optional[str] = None
