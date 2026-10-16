"""Structured output shapes for each capability.

Every capability asks the model for a typed object rather than prose.
Three things follow from that, and all three matter more than the
convenience:

- the backend gets something it can render, not a paragraph it has to
  parse;
- the shape itself is a prompt — a field called `evidence` asks for the
  figure a claim rests on more effectively than a sentence in the system
  message asking the model to cite things;
- a missing required field is a validation error rather than a plausible
  paragraph with nothing behind it.

camelCase on the wire, matching the backend's `CamelModel` convention,
so a field crosses both services without being renamed.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Priority = Literal["high", "medium", "low"]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class Insight(CamelModel):
    """One thing worth knowing, and the number that makes it true."""

    title: str = Field(description="One short sentence, specific and quantified.")
    detail: str = Field(description="Two or three sentences explaining why it matters.")
    severity: Priority = Field(description="How much attention this deserves.")
    evidence: str = Field(
        description=(
            "The exact figures from tool output that support this, e.g. "
            "'Shopping ₹48,000 vs usual ₹4,200'. Never a number you worked out yourself."
        )
    )


class Action(CamelModel):
    """Something the household could actually do this week."""

    title: str = Field(description="An imperative instruction, e.g. 'Move the iPhone EMI forward'.")
    detail: str = Field(description="What to do and why, in plain language.")
    priority: Priority
    expected_impact: str = Field(
        description=(
            "The concrete effect, in rupees or months where the tools give one, "
            "e.g. 'Clears ₹42,000 of 14.5% debt six months early'. "
            "Say 'not quantifiable from the data' rather than inventing a figure."
        )
    )


class BaseNarrative(CamelModel):
    """What every capability returns. Specialisations add to it."""

    headline: str = Field(description="One sentence a person could read on its own.")
    summary: str = Field(description="A short paragraph. Plain language, no jargon, no hedging.")
    insights: list[Insight] = Field(default_factory=list, max_length=6)
    actions: list[Action] = Field(default_factory=list, max_length=5)
    data_gaps: list[str] = Field(
        default_factory=list,
        max_length=4,
        description=(
            "What the household would have to record for this answer to get better, "
            "e.g. 'No monthly budget is set'. Empty when nothing is missing."
        ),
    )


# ------------------------------------------------------- 1. categorise
class CategoryAssignment(CamelModel):
    transaction_id: int
    category_name: str = Field(
        description="Must be spelled exactly as it appears in availableCategories."
    )
    confidence: float = Field(ge=0, le=1, description="How sure you are, 0 to 1.")
    reason: str = Field(description="Why, in one short sentence.")


class CategorisationResult(BaseNarrative):
    assignments: list[CategoryAssignment] = Field(
        default_factory=list,
        description=(
            "Only the rows from needsYourJudgement. Leave a row out entirely rather "
            "than guessing at it — an unassigned row costs the user a click, a wrong "
            "one corrupts every category total that follows."
        ),
    )
    skipped: list[str] = Field(
        default_factory=list,
        description="Descriptions of rows you deliberately did not assign, and why.",
    )


# -------------------------------------------------------- 2. anomalies
class AnomalyNarrative(BaseNarrative):
    verdict: Literal["nothing_unusual", "worth_a_look", "needs_attention"]
    total_unusual_spend: float = Field(
        default=0, description="Sum of the `excess` field across the findings you judged real."
    )


# ----------------------------------------------------------- 3. budget
class BudgetNarrative(BaseNarrative):
    status: Literal["on_track", "ahead_of_pace", "over_budget", "no_budget"]
    projected_overrun: float = Field(
        default=0, description="Copy `projectedOverrun` from the tool. Do not recompute it."
    )
    safe_daily_spend: float = Field(
        default=0, description="Copy `safeDailyRateForRest` from the tool."
    )


# --------------------------------------------------------- 4. forecast
class ForecastNarrative(BaseNarrative):
    expected: float = Field(description="Copy `expected` from the tool.")
    low: float
    high: float
    confidence: Literal["high", "medium", "low"]
    committed_share_pct: float = Field(
        default=0, description="What share of the forecast is already committed."
    )


# -------------------------------------------------- 5 & 6. investments
class PortfolioNarrative(BaseNarrative):
    net_worth: float = Field(description="Copy `netWorth` from the tool.")
    diversification_verdict: str = Field(
        description="One sentence on how concentrated the portfolio is."
    )
    debt_verdict: str = Field(
        description="One sentence on whether the debt load is a problem, and which loan matters most."
    )


# ------------------------------------------------- 6 & 7. obligations
class ObligationsNarrative(BaseNarrative):
    total_due: float = Field(description="Copy `totalDue` from the tool.")
    due_next_seven_days: float = Field(default=0)
    overdue_count: int = Field(default=0)
    cash_needed_warning: Optional[str] = Field(
        default=None,
        description=(
            "Set only when what is due soon looks large against the household's usual "
            "surplus. Otherwise null."
        ),
    )


# ----------------------------------------------------------- 8. report
class ReportSection(CamelModel):
    heading: str
    body: str = Field(description="Two to five sentences. Every figure from tool output.")


class MonthlyReportNarrative(BaseNarrative):
    month: str = Field(description="The month reported on, as 'YYYY-MM'.")
    sections: list[ReportSection] = Field(
        min_length=3,
        max_length=7,
        description=(
            "The report body. Cover income and outflow, where the money went, budget "
            "adherence, savings and investments, and what changed since last month."
        ),
    )
    grade: Literal["excellent", "good", "fair", "concerning"] = Field(
        description="How the month went overall, judged against this household's own history."
    )


# -------------------------------------------------- 9. recommendations
class Recommendation(Action):
    goal_name: Optional[str] = Field(
        default=None, description="The goal this serves, or null if it is structural."
    )
    horizon: Literal["this_week", "this_month", "this_quarter"]


class RecommendationsNarrative(BaseNarrative):
    recommendations: list[Recommendation] = Field(min_length=1, max_length=6)
    monthly_surplus: float = Field(description="Copy `surplus.surplus` from the goals tool.")
    feasible: bool = Field(
        description="Copy `feasible` — whether every goal's required monthly fits the surplus."
    )


# ------------------------------------------------------------ free-form
class AnswerNarrative(BaseNarrative):
    answer: str = Field(description="The direct answer to what was asked, first.")
    figures_used: list[str] = Field(
        default_factory=list,
        description="The tool figures the answer rests on, e.g. 'September spend ₹167,896'.",
    )


CAPABILITY_SCHEMAS: dict[str, type[BaseNarrative]] = {
    "categorise": CategorisationResult,
    "anomalies": AnomalyNarrative,
    "budget": BudgetNarrative,
    "forecast": ForecastNarrative,
    "investments": PortfolioNarrative,
    "obligations": ObligationsNarrative,
    "bills": ObligationsNarrative,
    "report": MonthlyReportNarrative,
    "recommendations": RecommendationsNarrative,
    "ask": AnswerNarrative,
}
