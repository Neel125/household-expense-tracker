"""Savings goals and their contributions."""
from sqlmodel import Session

from app.models import Goal
from app.models.mixins import now_iso
from app.repositories.repositories import GoalRepository
from app.schemas.goal import GoalIn
from app.services.errors import NotFoundError, ValidationError


class GoalService:
    def __init__(self, session: Session) -> None:
        self.goals = GoalRepository(session)

    def list(self, household_id: int):
        return self.goals.list(household_id)

    def create(self, household_id: int, data: GoalIn) -> Goal:
        if not data.name.strip():
            raise ValidationError("A goal needs a name")
        if data.target_amount <= 0:
            raise ValidationError("A goal needs a target amount")
        return self.goals.add(
            Goal(
                household_id=household_id,
                name=data.name.strip(),
                kind=data.kind or "custom",
                target_amount=float(data.target_amount or 0),
                saved_amount=max(0.0, float(data.saved_amount or 0)),
                target_date=data.target_date.strip(),
                created_at=now_iso(),
            )
        )

    def update(self, household_id: int, goal_id: int, data: GoalIn) -> Goal:
        goal = self.goals.get(household_id, goal_id)
        if not goal:
            raise NotFoundError("Goal not found")
        if not data.name.strip():
            raise ValidationError("A goal needs a name")
        goal.name = data.name.strip()
        goal.kind = data.kind or "custom"
        goal.target_amount = float(data.target_amount or 0)
        goal.saved_amount = max(0.0, float(data.saved_amount or 0))
        goal.target_date = data.target_date.strip()
        goal.updated_at = now_iso()
        return self.goals.save(goal)

    def contribute(self, household_id: int, goal_id: int, amount: float) -> Goal:
        goal = self.goals.get(household_id, goal_id)
        if not goal:
            raise NotFoundError("Goal not found")
        goal.saved_amount = max(0.0, goal.saved_amount + float(amount or 0))
        goal.updated_at = now_iso()
        return self.goals.save(goal)

    def delete(self, household_id: int, goal_id: int) -> None:
        goal = self.goals.get(household_id, goal_id)
        if not goal:
            raise NotFoundError("Goal not found")
        self.goals.delete(goal)
