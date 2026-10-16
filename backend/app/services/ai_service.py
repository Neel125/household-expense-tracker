"""Client for the household finance agent service.

The agent runs as its own container (`ai-agent/`) because LangChain and
its dependency tree have no business in the API image, and because an
analysis that takes thirty seconds should not occupy a worker that is
also serving the transaction list.

This module is the only place that knows the agent exists. Two rules
hold it together:

- **The household id comes from the authenticated user, never from the
  request body.** It is passed here as an argument and written onto the
  outbound payload here. There is no code path by which a client can
  name a household.
- **The agent is optional.** If it is not configured or not reachable,
  every other part of the app keeps working and these endpoints return a
  clean 503. A family's expense tracker must not stop working because an
  LLM service is down.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.services.errors import DomainError, ValidationError

log = logging.getLogger(__name__)

# Matches the agent's own MAX_HISTORY_TURNS. Both ends enforce it: this
# one keeps the request small, the agent's keeps the prompt small.
MAX_HISTORY_TURNS = 6


class AgentUnavailable(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=503)


class AgentFailed(DomainError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message, status_code=status_code)


class AiService:
    """Thin async HTTP client. Stateless — construct one per request."""

    def __init__(self) -> None:
        self.base_url = settings.agent_service_url.rstrip("/")
        self.token = settings.agent_service_token

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _require_configured(self) -> None:
        if not self.configured:
            raise AgentUnavailable(
                "The AI assistant is not configured on this deployment. "
                "Set AGENT_SERVICE_URL and AGENT_SERVICE_TOKEN."
            )

    async def _post(self, path: str, payload: dict, timeout: float) -> dict:
        self._require_configured()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.token}"},
                )
        except httpx.TimeoutException as exc:
            raise AgentFailed(
                "The AI assistant took too long to answer. Try again in a moment.",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            log.warning("agent service unreachable: %s", exc)
            raise AgentUnavailable("The AI assistant is not reachable right now.") from exc

        if response.status_code >= 400:
            # The agent's own messages are written for a person ("this
            # household has no transactions yet"), so they are passed
            # through rather than replaced with something vaguer.
            detail = _detail(response)
            if response.status_code in (401, 403):
                log.error("agent service rejected our token (%s)", response.status_code)
                raise AgentUnavailable("The AI assistant is misconfigured on this deployment.")
            raise AgentFailed(detail, status_code=response.status_code)

        return response.json()

    async def _get(self, path: str, timeout: float = 10.0) -> Any:
        self._require_configured()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.base_url}{path}",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
        except httpx.HTTPError as exc:
            raise AgentUnavailable("The AI assistant is not reachable right now.") from exc
        if response.status_code >= 400:
            raise AgentFailed(_detail(response), status_code=response.status_code)
        return response.json()

    # ----------------------------------------------------------- the API
    async def capabilities(self) -> list[dict]:
        return await self._get("/capabilities")

    async def analysis(
        self,
        household_id: int,
        capability: str,
        *,
        month: Optional[str] = None,
        horizon_days: int = 45,
    ) -> dict:
        """Deterministic figures. No LLM call, so this is cheap enough to
        put behind a dashboard card."""
        return await self._post(
            f"/analysis/{capability}",
            _payload(household_id, month=month, horizon_days=horizon_days),
            timeout=settings.agent_analysis_timeout,
        )

    async def run(
        self,
        household_id: int,
        capability: str,
        *,
        month: Optional[str] = None,
        horizon_days: int = 45,
        question: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> dict:
        """Run the agent. Much slower than the analysis endpoints — it is
        a multi-step run against a local model — so those are the right
        choice when figures alone will do."""
        if capability == "ask" and not (question or "").strip():
            raise ValidationError("Ask the assistant a question first")
        payload = _payload(household_id, month=month, horizon_days=horizon_days)
        if question:
            payload["question"] = question.strip()
        if history:
            # Trimmed here as well as in the agent: a client that sends a
            # thousand turns should cost one request, not one enormous one.
            payload["history"] = [
                {"question": str(t["question"])[:1000], "answer": str(t["answer"])[:4000]}
                for t in history[-MAX_HISTORY_TURNS:]
                if (t.get("question") or "").strip() and (t.get("answer") or "").strip()
            ]
        return await self._post(
            f"/agent/{capability}", payload, timeout=settings.agent_run_timeout
        )


def _payload(household_id: int, *, month: Optional[str], horizon_days: int) -> dict:
    payload: dict[str, Any] = {
        # Set here, from the authenticated user. Never from the client.
        "householdId": household_id,
        "horizonDays": max(1, min(int(horizon_days or 45), 180)),
    }
    if month:
        payload["month"] = month
    return payload


def _detail(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return f"The AI assistant returned an error ({response.status_code})."
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, list) and detail:
        # FastAPI validation errors arrive as a list of dicts.
        first = detail[0]
        return str(first.get("msg", first)) if isinstance(first, dict) else str(first)
    return str(detail) if detail else f"The AI assistant returned an error ({response.status_code})."
