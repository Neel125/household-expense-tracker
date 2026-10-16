"""DTOs for the AI agent endpoints.

The request carries no household id. The backend takes that from the
authenticated user and puts it on the wire itself — see
`app/services/ai_service.py`. A client that could name a household could
read another family's books.
"""
from typing import Any, Optional

from app.schemas.base import CamelModel


class AiChatTurn(CamelModel):
    """One earlier exchange in an assistant conversation."""

    question: str
    answer: str


class AiRequest(CamelModel):
    month: Optional[str] = None  # "YYYY-MM"; defaults per capability
    horizon_days: int = 45
    question: Optional[str] = None  # only the `ask` capability uses this
    # The agent holds no conversation state — it rebuilds the household's
    # books from scratch on every call — so follow-up questions only work
    # if the client sends what was said before. The chat page keeps the
    # transcript; this is how it reaches the model.
    history: list[AiChatTurn] = []


class AiMeta(CamelModel):
    model: str = ""
    tool_calls: list[str] = []
    steps: int = 0
    duration_ms: int = 0
    truncated: bool = False


class AiResponse(CamelModel):
    """The agent's typed narrative. `result` is capability-shaped — see
    the agent service's schemas — so it stays a free-form object here
    rather than being restated (and drifting) in two places."""

    capability: str
    month: Optional[str] = None
    result: dict[str, Any]
    meta: AiMeta


class AiAnalysisResponse(CamelModel):
    """Deterministic figures, no model involved."""

    capability: str
    as_of: str
    data: dict[str, Any]


class AiCapability(CamelModel):
    name: str
    summary: str
    needs_month: bool
    uses_subagents: bool
