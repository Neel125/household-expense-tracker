"""HTTP routes for the AI assistant.

Thin, like every other controller here: take the authenticated user,
hand their household id to the service, return what comes back. The one
rule worth stating is that `user.household_id` is the only source of the
household — no route accepts one from the caller.
"""
from fastapi import APIRouter, Path, Query

from app.core.deps import CurrentUser
from app.schemas.ai import (
    AiAnalysisResponse,
    AiCapability,
    AiMeta,
    AiRequest,
    AiResponse,
)
from app.services.ai_service import AiService

router = APIRouter(prefix="/ai", tags=["ai"])

CAPABILITY = Path(
    description=(
        "categorise | anomalies | budget | forecast | investments | "
        "obligations | bills | report | recommendations | ask"
    )
)


@router.get("/capabilities", response_model=list[AiCapability])
async def capabilities(user: CurrentUser) -> list[AiCapability]:
    """What the assistant can do, and which inputs each capability wants."""
    rows = await AiService().capabilities()
    return [AiCapability.model_validate(row) for row in rows]


@router.get("/analysis/{capability}", response_model=AiAnalysisResponse)
async def analysis(
    user: CurrentUser,
    capability: str = CAPABILITY,
    month: str | None = Query(default=None, description="'YYYY-MM'"),
    horizon_days: int = Query(default=45, ge=1, le=180, alias="horizonDays"),
) -> AiAnalysisResponse:
    """The numbers behind a capability, with no model involved.

    Deterministic and fast — this is what a dashboard card or a chart
    should call. `/ai/{capability}` is for when the household wants
    the numbers explained.
    """
    body = await AiService().analysis(
        user.household_id, capability, month=month, horizon_days=horizon_days
    )
    return AiAnalysisResponse(
        capability=body.get("capability", capability),
        as_of=str(body.get("asOf", "")),
        data=body.get("data", {}),
    )


@router.post("/{capability}", response_model=AiResponse)
async def run(
    user: CurrentUser,
    payload: AiRequest,
    capability: str = CAPABILITY,
) -> AiResponse:
    """Run the agent and return its narrative for this household."""
    body = await AiService().run(
        user.household_id,
        capability,
        month=payload.month,
        horizon_days=payload.horizon_days,
        question=payload.question,
        history=[t.model_dump() for t in payload.history],
    )
    return AiResponse(
        capability=body.get("capability", capability),
        month=body.get("month"),
        result=body.get("result", {}),
        meta=AiMeta.model_validate(body.get("meta", {})),
    )
