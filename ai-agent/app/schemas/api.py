"""Request and response DTOs.

camelCase on the wire, matching the backend's convention, so a field
name survives the hop between the two services unchanged.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class AnalysisRequest(CamelModel):
    """What the backend sends. `householdId` is the tenancy boundary and
    the backend has already resolved it from the caller's token — this
    service never sees an end user."""

    household_id: int = Field(gt=0)
    month: Optional[str] = Field(
        default=None,
        description="'YYYY-MM'. Defaults to the current month, or last month for reports.",
    )
    horizon_days: int = Field(default=45, ge=1, le=180)
    as_of: Optional[date] = Field(
        default=None,
        description=(
            "Treat this date as today. Only for tests and back-dated reports; "
            "production leaves it unset."
        ),
    )

    @field_validator("month")
    @classmethod
    def _valid_month(cls, value: Optional[str]) -> Optional[str]:
        if value in (None, ""):
            return None
        if not MONTH_PATTERN.match(value):
            raise ValueError("month must look like 'YYYY-MM'")
        return value


class ChatTurn(CamelModel):
    """One earlier exchange, replayed so a follow-up makes sense."""

    question: str = Field(max_length=1000)
    answer: str = Field(max_length=4000)


class AgentRequest(AnalysisRequest):
    question: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Required by the `ask` capability, ignored by the others.",
    )
    history: list[ChatTurn] = Field(
        default_factory=list,
        max_length=20,
        description=(
            "Earlier turns of the same conversation, oldest first. Only `ask` uses "
            "them. The service keeps no state of its own, so a client that wants "
            "follow-up questions to work has to send what was said before."
        ),
    )


class AgentMeta(CamelModel):
    model: str
    tool_calls: list[str] = Field(default_factory=list)
    steps: int = 0
    duration_ms: int = 0
    truncated: bool = False
    restated: bool = False
    """True when the model answered in prose and the structured result had
    to be recovered in a second, schema-constrained call."""


class AgentResponse(CamelModel):
    capability: str
    household_id: int
    month: Optional[str] = None
    result: dict[str, Any]
    meta: AgentMeta


class AnalysisResponse(CamelModel):
    """The deterministic half: the same figures the agent reasons over,
    with no model involved."""

    capability: str
    household_id: int
    as_of: date
    data: dict[str, Any]


class CapabilityInfo(CamelModel):
    name: str
    summary: str
    needs_month: bool
    uses_subagents: bool


class HealthResponse(CamelModel):
    status: str
    database: str
    llm_configured: bool
    model: str
