from typing import Optional

from app.schemas.base import CamelModel


class DebtIn(CamelModel):
    name: str
    kind: str = "other"
    lender: str = ""
    principal: float = 0
    outstanding: float = 0
    annual_rate_pct: float = 0
    emi: float = 0
    tenure_months: int = 0
    months_paid: int = 0
    start_date: str = ""
    notes: str = ""


class DebtOut(CamelModel):
    id: int
    name: str
    kind: str
    lender: str
    principal: float
    outstanding: float
    annual_rate_pct: float
    emi: float
    tenure_months: int
    months_paid: int
    start_date: str
    notes: str
    created_at: str = ""
    updated_at: Optional[str] = None
