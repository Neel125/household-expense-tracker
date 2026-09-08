"""Spending categories: predefined (seeded at household creation) plus
custom ones the user adds."""
from sqlmodel import Session

from app.models import Category
from app.models.mixins import now_iso
from app.repositories.repositories import CategoryRepository, TransactionRepository
from app.schemas.category import CategoryIn
from app.services.errors import ConflictError, NotFoundError, ValidationError

_PALETTE = [f"var(--series-{i})" for i in range(1, 7)]


class CategoryService:
    def __init__(self, session: Session) -> None:
        self.categories = CategoryRepository(session)
        self.transactions = TransactionRepository(session)

    def list(self, household_id: int):
        return self.categories.list(household_id)

    def create(self, household_id: int, data: CategoryIn) -> Category:
        name = data.name.strip()
        if not name:
            raise ValidationError("A category needs a name")
        existing = self.categories.list(household_id)
        if any(c.name.casefold() == name.casefold() for c in existing):
            raise ConflictError(f"'{name}' already exists")
        color = data.color or _PALETTE[len(existing) % len(_PALETTE)]
        return self.categories.add(
            Category(
                household_id=household_id,
                name=name,
                color=color,
                is_custom=True,
                sort_order=len(existing),
                created_at=now_iso(),
            )
        )

    def update(self, household_id: int, category_id: int, data: CategoryIn) -> Category:
        category = self.categories.get(household_id, category_id)
        if not category:
            raise NotFoundError("Category not found")
        name = data.name.strip()
        if not name:
            raise ValidationError("A category needs a name")
        clash = next(
            (
                c
                for c in self.categories.list(household_id)
                if c.name.casefold() == name.casefold() and c.id != category.id
            ),
            None,
        )
        if clash:
            raise ConflictError(f"'{name}' already exists")
        category.name = name
        if data.color:
            category.color = data.color
        category.archived = bool(data.archived)
        category.updated_at = now_iso()
        return self.categories.save(category)

    def delete(self, household_id: int, category_id: int) -> None:
        category = self.categories.get(household_id, category_id)
        if not category:
            raise NotFoundError("Category not found")
        in_use = any(
            t.category_id == category.id for t in self.transactions.list(household_id)
        )
        if in_use:
            raise ConflictError(
                "This category is used by transactions — archive it instead of deleting."
            )
        self.categories.delete(category)
