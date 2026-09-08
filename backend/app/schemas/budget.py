from typing import List

from app.schemas.base import CamelModel


class CategoryBudgetItem(CamelModel):
    category_id: int
    percentage: float = 0


class BudgetIn(CamelModel):
    monthly_budget: float = 0
    categories: List[CategoryBudgetItem] = []


class BudgetOut(CamelModel):
    monthly_budget: float
    categories: List[CategoryBudgetItem]
