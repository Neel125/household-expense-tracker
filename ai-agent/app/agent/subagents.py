"""The specialist analysts the main agent can delegate to.

Subagents earn their cost in exactly one situation: a task that spans
several domains and would otherwise force one context to hold the
spending breakdown, the whole portfolio and the goal maths at once. The
monthly report is that task. Checking a budget is not, which is why
`USES_SUBAGENTS` is a short list rather than "always".

Each analyst gets only the tools its remit needs. That is not a security
boundary — every tool is already bound to the same household — it is a
quality one. A subagent asked about debt while holding fourteen tools
spends its first turns deciding which to call; one holding four does not.

They run `isolated` (the default): each receives only the task it was
delegated, not the parent's conversation. For a report that is the point
— three analysts working from the same books and reaching their own
conclusions, which the main agent then reconciles into one document.
"""
from __future__ import annotations

from typing import Sequence

from deepagents import SubAgent
from langchain_core.tools import BaseTool

from app.agent import prompts
from app.agent.llm import subagent_model

# Capabilities that genuinely span domains. Everything else runs with no
# subagents at all, which also removes the `task` tool from its surface
# (see app/agent/llm.py).
USES_SUBAGENTS = frozenset({"report", "recommendations", "ask"})

SPENDING_TOOLS = (
    "get_household_overview",
    "get_spending_by_category",
    "detect_spending_anomalies",
    "get_budget_status",
    "compare_months",
    "list_transactions",
    "get_recurring_payments",
)
PORTFOLIO_TOOLS = (
    "get_household_overview",
    "analyse_portfolio",
    "get_credit_card_balances",
    "get_upcoming_obligations",
    "list_transactions",
)
PLANNING_TOOLS = (
    "get_household_overview",
    "forecast_next_month",
    "get_upcoming_obligations",
    "get_goal_progress",
    "get_recurring_payments",
    "get_budget_status",
)


def _subset(tools: Sequence[BaseTool], names: Sequence[str]) -> list[BaseTool]:
    by_name = {t.name: t for t in tools}
    return [by_name[n] for n in names if n in by_name]


def build_subagents(tools: Sequence[BaseTool]) -> list[SubAgent]:
    """The three analysts, each bound to the same household's tools."""
    return [
        SubAgent(
            name="spending-analyst",
            description=(
                "Delegate questions about where the money went: category breakdowns, "
                "unusual or duplicated spending, budget adherence, month-on-month "
                "changes, and uncategorised transactions. Give it one specific "
                "question and the month to answer it for."
            ),
            system_prompt=prompts.SPENDING_ANALYST,
            tools=_subset(tools, SPENDING_TOOLS),
            model=subagent_model(),
        ),
        SubAgent(
            name="portfolio-analyst",
            description=(
                "Delegate questions about what the household owns and owes: holdings, "
                "valuations, allocation and concentration, stalled SIPs, maturing "
                "deposits, loan balances, interest still to run, and credit-card "
                "outstanding. Give it one specific question."
            ),
            system_prompt=prompts.PORTFOLIO_ANALYST,
            tools=_subset(tools, PORTFOLIO_TOOLS),
            model=subagent_model(),
        ),
        SubAgent(
            name="planning-analyst",
            description=(
                "Delegate forward-looking questions: next month's forecast, bills and "
                "instalments coming due, goal progress and feasibility, and the "
                "surplus available to fund any of it. Give it one specific question."
            ),
            system_prompt=prompts.PLANNING_ANALYST,
            tools=_subset(tools, PLANNING_TOOLS),
            model=subagent_model(),
        ),
    ]
