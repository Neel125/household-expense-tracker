from typing import Optional

from app.schemas.base import CamelModel


class TransactionIn(CamelModel):
    date: str
    name: str
    type: str
    amount: float
    payment_mode: str = ""
    provider_type: str = ""
    necessity: str = ""
    account: str = ""
    member: str = ""
    category_id: Optional[int] = None
    merchant: str = ""
    investment_id: Optional[int] = None
    debt_id: Optional[int] = None


class TransactionOut(CamelModel):
    id: int
    date: str
    name: str
    type: str
    amount: float
    payment_mode: str
    provider_type: str
    necessity: str
    account: str
    member: str
    category_id: Optional[int] = None
    merchant: str
    investment_id: Optional[int] = None
    debt_id: Optional[int] = None
    created_at: str = ""
    updated_at: Optional[str] = None
