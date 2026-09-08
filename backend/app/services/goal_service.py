"""Savings goals and their contributions."""
from typing import Optional

from sqlmodel import Session

from app.models import Goal
from app.models.mixins import now_iso
from app.repositories.repositories import GoalRepository
from app.schemas.goal import GoalIn
from app.services import events
from app.services.errors import NotFoundError, ValidationError


class GoalService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.goals = GoalRepository(session)

    def list(self, household_id: int):
        return self.goals.list(household_id)

    def create(
        self, household_id: int, data: GoalIn, actor_id: Optional[int] = None
    ) -> Goal:
        if not data.name.strip():
            raise ValidationError("A goal needs a name")
        if data.target_amount <= 0:
            raise ValidationError("A goal needs a target amount")
        goal = self.goals.add(
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
        return self._announce(goal, actor_id)

    def update(
        self, household_id: int, goal_id: int, data: GoalIn, actor_id: Optional[int] = None
    ) -> Goal:
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
        return self._announce(self.goals.save(goal), actor_id)

    def contribute(
        self, household_id: int, goal_id: int, amount: float, actor_id: Optional[int] = None
    ) -> Goal:
        goal = self.goals.get(household_id, goal_id)
        if not goal:
            raise NotFoundError("Goal not found")
        goal.saved_amount = max(0.0, goal.saved_amount + float(amount or 0))
        goal.updated_at = now_iso()
        return self._announce(self.goals.save(goal), actor_id)

    def _announce(self, goal: Goal, actor_id: Optional[int]) -> Goal:
        """A goal that has reached its target is a fact worth publishing —
        the rewards engine pays for it, and its idempotency key means
        crossing the line twice (by editing the target down and back) is
        only ever paid once."""
        if goal.target_amount > 0 and goal.saved_amount >= goal.target_amount:
            events.publish(
                self.session,
                events.DomainEvent(
                    name=events.GOAL_COMPLETED,
                    household_id=goal.household_id,
                    user_id=actor_id,
                    payload={"goal_id": goal.id, "name": goal.name},
                ),
            )
        return goal

    def delete(self, household_id: int, goal_id: int) -> None:
        goal = self.goals.get(household_id, goal_id)
        if not goal:
            raise NotFoundError("Goal not found")
        self.goals.delete(goal)
