from typing import Optional

from app.schemas.base import CamelModel


class CategoryIn(CamelModel):
    name: str
    color: str = ""
    archived: bool = False


class CategoryOut(CamelModel):
    id: int
    name: str
    color: str
    is_custom: bool
    archived: bool
    sort_order: int
    created_at: str = ""
    updated_at: Optional[str] = None
