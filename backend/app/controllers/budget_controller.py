from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.budget import BudgetIn, BudgetOut
from app.services.budget_service import BudgetService

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("", response_model=BudgetOut)
def get_budget(user: CurrentUser, session: SessionDep) -> BudgetOut:
    return BudgetService(session).get(user.household_id)


@router.put("", response_model=BudgetOut)
def update_budget(payload: BudgetIn, user: CurrentUser, session: SessionDep) -> BudgetOut:
    return BudgetService(session).replace(user.household_id, payload)
