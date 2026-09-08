"""The household's monthly budget and how it is split across categories
(as percentages). Read/replace as a single document for simplicity."""
from sqlmodel import Session

from app.models import CategoryBudget
from app.models.mixins import now_iso
from app.repositories.repositories import (
    CategoryBudgetRepository,
    CategoryRepository,
    HouseholdRepo,
)
from app.schemas.budget import BudgetIn, BudgetOut, CategoryBudgetItem
from app.services.errors import NotFoundError, ValidationError


class BudgetService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.households = HouseholdRepo(session)
        self.category_budgets = CategoryBudgetRepository(session)
        self.categories = CategoryRepository(session)

    def get(self, household_id: int) -> BudgetOut:
        household = self.households.get(household_id)
        if not household:
            raise NotFoundError("Household not found")
        items = [
            CategoryBudgetItem(category_id=b.category_id, percentage=b.percentage)
            for b in self.category_budgets.list(household_id)
        ]
        return BudgetOut(monthly_budget=household.monthly_budget, categories=items)

    def replace(self, household_id: int, data: BudgetIn) -> BudgetOut:
        household = self.households.get(household_id)
        if not household:
            raise NotFoundError("Household not found")

        total_pct = sum(max(0.0, i.percentage) for i in data.categories)
        if total_pct > 100.0001:
            raise ValidationError(
                f"Category budgets add up to {round(total_pct)}% — that's over 100%."
            )

        valid_ids = {c.id for c in self.categories.list(household_id)}
        household.monthly_budget = max(0.0, float(data.monthly_budget or 0))
        household.updated_at = now_iso()
        self.session.add(household)

        # Replace the whole set: drop existing rows, insert the new ones.
        for existing in self.category_budgets.list(household_id):
            self.session.delete(existing)
        now = now_iso()
        for item in data.categories:
            if item.category_id not in valid_ids or item.percentage <= 0:
                continue
            self.session.add(
                CategoryBudget(
                    household_id=household_id,
                    category_id=item.category_id,
                    percentage=max(0.0, min(100.0, item.percentage)),
                    created_at=now,
                )
            )
        self.session.commit()
        return self.get(household_id)
