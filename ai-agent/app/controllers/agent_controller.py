"""The service's HTTP surface.

Two parallel families of endpoint over the same data, and the split is
the most useful thing about this service's shape:

- **`/analysis/{capability}`** returns the deterministic figures alone.
  No model is called and the answer is identical on every run. This is
  what the backend should use to draw a chart, to populate a dashboard
  card, or to test any of this without an Ollama host running.
- **`/agent/{capability}`** runs the deep agent over exactly those same
  figures and returns a typed narrative: what they mean, what is worth
  worrying about, and what to do.

A caller that wants numbers should never pay for tokens to get them, and
a caller that wants judgement gets it grounded in numbers it can fetch
separately and check. Keeping both halves addressable is what makes that
possible.
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Path

from app.agent.llm import LLMNotConfigured
from app.agent.runner import AgentError, AgentTimeout
from app.agent.runner import run as run_agent
from app.agent.subagents import USES_SUBAGENTS
from app.core.deps import SessionDep
from app.core.security import require_service_token
from app.data.snapshot import HouseholdNotFound, HouseholdSnapshot, load_snapshot
from app.finance import (
    anomaly,
    budget as budget_mod,
    categorize,
    forecast as forecast_mod,
    goals as goals_mod,
    obligations as obligations_mod,
    portfolio as portfolio_mod,
    recurring as recurring_mod,
    report as report_mod,
)
from app.finance.month import prev_month_key, this_month_key
from app.schemas.api import (
    AgentMeta,
    AgentRequest,
    AgentResponse,
    AnalysisRequest,
    AnalysisResponse,
    CapabilityInfo,
)

router = APIRouter(dependencies=[Depends(require_service_token)])

CAPABILITY_SUMMARIES: dict[str, str] = {
    "categorise": "Suggest categories for uncategorised expenses.",
    "anomalies": "Find spending that is unusual for this household.",
    "budget": "Track the monthly budget, per category and overall.",
    "forecast": "Forecast next month's expenses, committed and variable.",
    "investments": "Analyse holdings, allocation, returns and debts.",
    "obligations": "Monitor SIPs, deposits, loans and credit cards.",
    "bills": "Identify the bills and instalments coming due.",
    "report": "Write the monthly financial report.",
    "recommendations": "Recommend actions against the household's own goals.",
    "ask": "Answer a free-form question about this household's finances.",
}
NEEDS_MONTH = {"categorise", "anomalies", "budget", "forecast", "report"}


# --------------------------------------------------------------- helpers
def _snapshot(session, household_id: int, as_of: Optional[date]) -> HouseholdSnapshot:
    try:
        return load_snapshot(session, household_id, as_of)
    except HouseholdNotFound as exc:
        raise HTTPException(404, str(exc)) from exc


def _capability(value: str) -> str:
    if value not in CAPABILITY_SUMMARIES:
        raise HTTPException(
            404,
            f"Unknown capability '{value}'. Known: {', '.join(sorted(CAPABILITY_SUMMARIES))}",
        )
    return value


# ------------------------------------------------------------- discovery
@router.get("/capabilities", response_model=list[CapabilityInfo], tags=["meta"])
def capabilities() -> list[CapabilityInfo]:
    return [
        CapabilityInfo(
            name=name,
            summary=summary,
            needs_month=name in NEEDS_MONTH,
            uses_subagents=name in USES_SUBAGENTS,
        )
        for name, summary in CAPABILITY_SUMMARIES.items()
    ]


# ------------------------------------------------------- deterministic
def _analysis(capability: str, snapshot: HouseholdSnapshot, payload: AnalysisRequest) -> dict:
    """The figures, with no model involved."""
    month = payload.month or this_month_key(snapshot.as_of)

    def categorise() -> dict:
        resolved, unresolved = categorize.suggest(snapshot)
        return {
            "coverage": categorize.coverage(snapshot),
            "suggestions": [s.as_dict() for s in resolved],
            "needsJudgement": [
                {
                    "transactionId": t.id,
                    "date": t.date,
                    "name": t.name,
                    "merchant": t.merchant,
                    "amount": round(float(t.amount or 0), 2),
                }
                for t in unresolved
            ],
            "availableCategories": [
                {"id": c.id, "name": c.name} for c in snapshot.active_categories
            ],
        }

    def obligations() -> dict:
        return obligations_mod.summary(snapshot, payload.horizon_days)

    builders: dict[str, Callable[[], dict]] = {
        "categorise": categorise,
        "anomalies": lambda: {
            "month": month,
            "anomalies": [a.as_dict() for a in anomaly.detect(snapshot, month)],
        },
        "budget": lambda: budget_mod.status(snapshot, month).as_dict(),
        "forecast": lambda: forecast_mod.forecast(snapshot, month).as_dict(),
        "investments": lambda: portfolio_mod.analyse(snapshot).as_dict(),
        "obligations": obligations,
        "bills": obligations,
        "report": lambda: report_mod.build(
            snapshot, payload.month or prev_month_key(this_month_key(snapshot.as_of))
        ),
        "recommendations": lambda: goals_mod.analyse(snapshot),
        "ask": lambda: {
            "detail": (
                "'ask' is a free-form question and has no deterministic form. "
                "Use POST /agent/ask, or one of the other /analysis capabilities."
            )
        },
    }
    return builders[capability]()


@router.post(
    "/analysis/{capability}", response_model=AnalysisResponse, tags=["analysis"]
)
def analysis(
    payload: AnalysisRequest,
    session: SessionDep,
    capability: str = Path(description="One of the names from GET /capabilities"),
) -> AnalysisResponse:
    """Deterministic figures only — no LLM call, identical on every run,
    milliseconds. Safe to call on every page load."""
    name = _capability(capability)
    snapshot = _snapshot(session, payload.household_id, payload.as_of)
    return AnalysisResponse(
        capability=name,
        household_id=payload.household_id,
        as_of=snapshot.as_of,
        data=_analysis(name, snapshot, payload),
    )


@router.post("/analysis/recurring/detect", response_model=AnalysisResponse, tags=["analysis"])
def recurring(payload: AnalysisRequest, session: SessionDep) -> AnalysisResponse:
    """Standing commitments detected from the ledger, active and lapsed."""
    snapshot = _snapshot(session, payload.household_id, payload.as_of)
    names = recurring_mod.record_names(snapshot)
    items = [
        r for r in recurring_mod.detect(snapshot) if not recurring_mod.covered_by_record(r, names)
    ]
    return AnalysisResponse(
        capability="recurring",
        household_id=payload.household_id,
        as_of=snapshot.as_of,
        data={
            "active": [r.as_dict() for r in items if r.active],
            "lapsed": [r.as_dict() for r in items if not r.active],
            "monthlyCommitted": round(sum(r.typical_amount for r in items if r.active), 2),
        },
    )


# -------------------------------------------------------------- the agent
@router.post("/agent/{capability}", response_model=AgentResponse, tags=["agent"])
async def agent(
    payload: AgentRequest,
    session: SessionDep,
    capability: str = Path(description="One of the names from GET /capabilities"),
) -> AgentResponse:
    """Run the deep agent over this household's books and return a typed
    narrative. Much slower — a multi-step run against a local model; use
    `/analysis/*` when figures alone will do."""
    name = _capability(capability)
    if name == "ask" and not (payload.question or "").strip():
        raise HTTPException(422, "The 'ask' capability needs a question")

    snapshot = _snapshot(session, payload.household_id, payload.as_of)
    # A household with nothing in it produces a confident-sounding
    # analysis of nothing, which is the single most misleading thing this
    # service could return. Refuse instead.
    if not snapshot.has_any_data():
        raise HTTPException(
            422,
            "This household has no transactions, investments, debts or goals yet — "
            "there is nothing to analyse.",
        )

    try:
        result = await run_agent(
            snapshot,
            name,
            month=payload.month,
            question=payload.question,
            horizon_days=payload.horizon_days,
            history=[(t.question, t.answer) for t in payload.history],
        )
    except LLMNotConfigured as exc:
        raise HTTPException(503, str(exc)) from exc
    except AgentTimeout as exc:
        raise HTTPException(504, str(exc)) from exc
    except AgentError as exc:
        raise HTTPException(502, str(exc)) from exc

    return AgentResponse(
        capability=name,
        household_id=payload.household_id,
        month=payload.month,
        result=result.result,
        meta=AgentMeta(
            model=result.model,
            tool_calls=result.tool_calls,
            steps=result.steps,
            duration_ms=result.duration_ms,
            truncated=result.truncated,
        ),
    )
