from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.goal import GoalContributionIn, GoalIn, GoalOut
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("", response_model=list[GoalOut])
def list_goals(user: CurrentUser, session: SessionDep) -> list[GoalOut]:
    service = GoalService(session)
    return [GoalOut.model_validate(g) for g in service.list(user.household_id)]


@router.post("", response_model=GoalOut, status_code=201)
def create_goal(payload: GoalIn, user: CurrentUser, session: SessionDep) -> GoalOut:
    service = GoalService(session)
    return GoalOut.model_validate(service.create(user.household_id, payload))


@router.put("/{goal_id}", response_model=GoalOut)
def update_goal(goal_id: int, payload: GoalIn, user: CurrentUser, session: SessionDep) -> GoalOut:
    service = GoalService(session)
    return GoalOut.model_validate(service.update(user.household_id, goal_id, payload))


@router.post("/{goal_id}/contribute", response_model=GoalOut)
def contribute(goal_id: int, payload: GoalContributionIn, user: CurrentUser, session: SessionDep) -> GoalOut:
    service = GoalService(session)
    return GoalOut.model_validate(service.contribute(user.household_id, goal_id, payload.amount))


@router.delete("/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: CurrentUser, session: SessionDep) -> Response:
    GoalService(session).delete(user.household_id, goal_id)
    return Response(status_code=204)
