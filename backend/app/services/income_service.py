"""Recurring monthly income sources (salary / other)."""
from sqlmodel import Session

from app.models import IncomeSource
from app.models.mixins import now_iso
from app.repositories.repositories import IncomeSourceRepository
from app.schemas.income import IncomeSourceIn
from app.services.errors import NotFoundError, ValidationError


class IncomeService:
    def __init__(self, session: Session) -> None:
        self.sources = IncomeSourceRepository(session)

    def list(self, household_id: int):
        return self.sources.list(household_id)

    def create(self, household_id: int, data: IncomeSourceIn) -> IncomeSource:
        if not data.name.strip():
            raise ValidationError("An income source needs a name")
        return self.sources.add(
            IncomeSource(
                household_id=household_id,
                name=data.name.strip(),
                kind=data.kind or "salary",
                monthly_amount=max(0.0, float(data.monthly_amount or 0)),
                member=data.member.strip(),
                active=bool(data.active),
                created_at=now_iso(),
            )
        )

    def update(self, household_id: int, source_id: int, data: IncomeSourceIn) -> IncomeSource:
        source = self.sources.get(household_id, source_id)
        if not source:
            raise NotFoundError("Income source not found")
        if not data.name.strip():
            raise ValidationError("An income source needs a name")
        source.name = data.name.strip()
        source.kind = data.kind or "salary"
        source.monthly_amount = max(0.0, float(data.monthly_amount or 0))
        source.member = data.member.strip()
        source.active = bool(data.active)
        source.updated_at = now_iso()
        return self.sources.save(source)

    def delete(self, household_id: int, source_id: int) -> None:
        source = self.sources.get(household_id, source_id)
        if not source:
            raise NotFoundError("Income source not found")
        self.sources.delete(source)
