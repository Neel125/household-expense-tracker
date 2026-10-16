"""HTTP layer. Thin: parse, load a snapshot, call one analysis or one
agent run, return a schema."""
from fastapi import APIRouter

from app.controllers.agent_controller import router as agent_router

api_router = APIRouter()
api_router.include_router(agent_router)
