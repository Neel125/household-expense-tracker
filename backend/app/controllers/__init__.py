"""HTTP layer. Each router is thin: parse -> call a service -> return a
schema. No business rules live here."""
from fastapi import APIRouter

from app.controllers.account_controller import router as account_router
from app.controllers.auth_controller import router as auth_router
from app.controllers.budget_controller import router as budget_router
from app.controllers.category_controller import router as category_router
from app.controllers.debt_controller import router as debt_router
from app.controllers.goal_controller import router as goal_router
from app.controllers.income_controller import router as income_router
from app.controllers.investment_controller import router as investment_router
from app.controllers.member_controller import router as member_router
from app.controllers.rewards_controller import router as rewards_router
from app.controllers.transaction_controller import router as transaction_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router)
api_router.include_router(transaction_router)
api_router.include_router(member_router)
api_router.include_router(account_router)
api_router.include_router(category_router)
api_router.include_router(budget_router)
api_router.include_router(income_router)
api_router.include_router(goal_router)
api_router.include_router(investment_router)
api_router.include_router(debt_router)
api_router.include_router(rewards_router)


@api_router.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
