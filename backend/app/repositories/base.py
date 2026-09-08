"""Generic, household-scoped data access.

One place that knows how to list/get/create/update/delete a table for a
given household. Per-entity repositories subclass this so business rules
never have to hand-write the same tenancy filter (DRY), and services can
depend on the small repository interface rather than SQLModel directly
(Dependency Inversion).
"""
from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlmodel import Session, SQLModel, select

ModelT = TypeVar("ModelT", bound=SQLModel)


class HouseholdRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: Type[ModelT]) -> None:
        self.session = session
        self.model = model

    def list(self, household_id: int) -> Sequence[ModelT]:
        stmt = select(self.model).where(self.model.household_id == household_id)
        return self.session.exec(stmt.order_by(self.model.id)).all()

    def get(self, household_id: int, obj_id: int) -> Optional[ModelT]:
        obj = self.session.get(self.model, obj_id)
        if obj is None or obj.household_id != household_id:
            return None
        return obj

    def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def save(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)
        self.session.commit()
