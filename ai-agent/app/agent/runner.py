"""Building and running the deep agent for one request.

The agent is constructed per request rather than cached, because its
tools are closures over one household's snapshot (see
`app/agent/tools.py`). Compiling a LangGraph is microseconds; the model
call that follows is seconds. Caching the graph would save nothing
measurable and would reintroduce the one bug worth designing against —
a tool bound to the wrong household.

Three guardrails bound what a run can cost:

- `recursion_limit` caps how many times the graph may loop, so a model
  that keeps calling tools stops instead of billing forever;
- `asyncio.wait_for` caps wall-clock time, because a run that has
  already taken two minutes is not going to produce a useful answer;
- the output schema is required, so a run that ends without one is
  reported as a failure rather than returned as an empty narrative.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from deepagents import FilesystemMiddleware, create_deep_agent
from langgraph.errors import GraphRecursionError
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import prompts
from app.agent.llm import LLMNotConfigured, main_model
from app.agent.schemas import CAPABILITY_SCHEMAS
from app.agent.subagents import USES_SUBAGENTS, build_subagents
from app.agent.tools import build_tools
from app.core.config import settings
from app.data.snapshot import HouseholdSnapshot

log = logging.getLogger(__name__)

CAPABILITIES = tuple(CAPABILITY_SCHEMAS)

# How much of a conversation is replayed. Each turn costs tokens on every
# subsequent question, and a household asking about last month rarely
# needs what was said eight questions ago.
MAX_HISTORY_TURNS = 6
# Prior answers are replayed as context, not as evidence, so only enough
# of each is kept to resolve a reference like "that category".
MAX_REPLAYED_ANSWER_CHARS = 1200

# Tool calls that are not evidence. The response tool is the answer
# itself; the rest are scaffolding — a scratchpad and the delegation
# tool, none of which can tell you what a household spent.
_NON_EVIDENCE_TOOLS = frozenset(
    {"task", "read_file", "write_file", "edit_file", "ls", "glob", "grep"}
)

# Below this, re-stating the answer would be cut off mid-generation and
# the run is better reported as unfinished.
_FINISH_MIN_SECONDS = 20.0

# A bracketed span that names a tool, or opens with a filler word, is the
# model describing where a figure *would* come from instead of copying
# it: "the following bills are coming up: [list from
# get_upcoming_obligations]". Observed verbatim from a small model on a
# run that otherwise passed every check — the tools were called and the
# schema validated, and the household would still have been shown that
# sentence. Deliberately narrow: ordinary prose rarely brackets a phrase
# that begins this way, and a false positive costs one re-run while a
# false negative puts a placeholder in front of a person.
_PLACEHOLDER = re.compile(
    r"\[(?:[^\]]{0,20}\b(?:list|insert|value|figure|number|amount|from|todo|tbd)\b"
    r"[^\]]{0,60}|get_[a-z_]+|analyse_[a-z_]+|compare_[a-z_]+|detect_[a-z_]+|forecast_[a-z_]+)\]",
    re.IGNORECASE,
)


def _placeholders(payload: dict) -> list[str]:
    """Every placeholder-looking span in the answer's text fields."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            found.extend(_PLACEHOLDER.findall(value))
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(payload)
    return found


class AgentError(RuntimeError):
    """A run that could not produce an answer."""


class AgentTimeout(AgentError):
    pass


@dataclass
class AgentResult:
    capability: str
    result: dict
    model: str
    tool_calls: list[str] = field(default_factory=list)
    steps: int = 0
    duration_ms: int = 0
    truncated: bool = False
    restated: bool = False
    """The model wrote its answer as prose and the schema was recovered in
    a second, constrained call. Worth surfacing: it marks a model that is
    struggling with this agent's output contract."""

    def as_dict(self) -> dict:
        return {
            "capability": self.capability,
            "result": self.result,
            "meta": {
                "model": self.model,
                "toolCalls": self.tool_calls,
                "steps": self.steps,
                "durationMs": self.duration_ms,
                "truncated": self.truncated,
                "restated": self.restated,
            },
        }


def _task_prompt(capability: str, *, month: Optional[str], question: Optional[str],
                 horizon_days: int, has_history: bool = False) -> str:
    builder = prompts.TASK_PROMPTS[capability]
    if capability == "ask":
        return builder(
            question or "Summarise how this household's finances are doing.",
            has_history=has_history,
        )
    if capability in ("obligations", "bills"):
        return builder(horizon_days)
    if capability == "investments":
        return builder()
    if capability == "recommendations":
        return builder()
    return builder(month)


def _conversation(task: str, history: Optional[Sequence[tuple[str, str]]]) -> list[Any]:
    """The message list an `ask` run starts from.

    Earlier turns are replayed as plain question/answer pairs — the tool
    calls that produced them are left out on purpose. Replaying those
    would multiply the context with every question and, worse, would put
    stale figures in front of the model as if they were current. The
    prompt tells it to call the tools again; this makes sure it has to.
    """
    messages: list[Any] = []
    for question, answer in (history or [])[-MAX_HISTORY_TURNS:]:
        question, answer = (question or "").strip(), (answer or "").strip()
        if not question or not answer:
            continue
        messages.append(HumanMessage(content=question))
        messages.append(AIMessage(content=answer[:MAX_REPLAYED_ANSWER_CHARS]))
    messages.append(HumanMessage(content=task))
    return messages


def _tool_calls(messages: list[Any]) -> list[str]:
    names: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                names.append(call.get("name", "?"))
    return names


async def _finish(capability: str, messages: list[Any], started: float):
    """Re-state an already-reasoned answer in the required schema.

    Small local models reliably do the analysis and then fail at the last
    step, writing the report as a chat message rather than calling the
    output tool. That is a formatting failure, not an analytical one, and
    the whole run — several minutes of tool calls on local hardware — is
    otherwise wasted.

    So this makes one more call, with the schema enforced by Ollama's
    `json_schema` format rather than offered as a tool. That is
    grammar-constrained decoding: the model cannot emit tokens that break
    the schema, which turns "will it remember to call the tool" into a
    non-question.

    It is deliberately weak by construction. It has **no tools**, so it
    cannot fetch anything new, and it sees only the conversation that
    already happened — every figure available to it came from a finance
    tool earlier in that conversation. It reformats; it cannot research,
    and it cannot reach past the books.
    """
    schema = CAPABILITY_SCHEMAS[capability]
    remaining = settings.timeout_seconds - (time.perf_counter() - started)
    if remaining < _FINISH_MIN_SECONDS:
        log.warning("no time left to re-state the %s answer (%.0fs)", capability, remaining)
        return None

    model = main_model().with_structured_output(schema, method="json_schema")
    instruction = HumanMessage(
        content=(
            "Restate the analysis you just gave as the structured answer.\n\n"
            "Use only figures that appear in the tool results above — copy them "
            "exactly. Do not calculate anything new, and do not add findings the "
            "tools did not show. If a field has no support in those results, "
            "leave it empty rather than filling it with a guess."
        )
    )
    try:
        return await asyncio.wait_for(
            model.ainvoke([*messages, instruction]), timeout=remaining
        )
    except Exception as exc:  # noqa: BLE001 - includes the timeout
        # A failed re-statement is not fatal: the caller reports the run
        # as unfinished, which is what would have happened anyway.
        log.warning("could not re-state the %s answer: %s", capability, exc)
        return None


def build_agent(snapshot: HouseholdSnapshot, capability: str):
    """One compiled agent, bound to one household, shaped for one task."""
    if capability not in CAPABILITY_SCHEMAS:
        raise AgentError(f"Unknown capability '{capability}'")

    tools = build_tools(snapshot)
    # Only the multi-domain capabilities get analysts. Elsewhere no
    # subagents are passed, which also removes the `task` tool entirely.
    delegates = capability in USES_SUBAGENTS
    subagents = build_subagents(tools) if delegates else None

    # The virtual filesystem is a drafting scratchpad: it earns its seven
    # tool schemas when the main agent is stitching three analysts'
    # findings into one report, and not otherwise. A capability that
    # makes two tool calls and answers does not need somewhere to put a
    # draft, so it gets the minimum the middleware allows (`read_file`
    # is required scaffolding and cannot be dropped). That takes the
    # narrow capabilities from 22 offered tools to 15 — fewer wrong
    # turns, less prompt, lower cost.
    middleware = [] if delegates else [FilesystemMiddleware(tools=["read_file"])]

    return create_deep_agent(
        model=main_model(),
        tools=tools,
        system_prompt=prompts.SYSTEM,
        subagents=subagents,
        middleware=middleware,
        # ToolStrategy rather than the provider's JSON mode: the agent is
        # already in a tool-calling loop, so asking for the answer as one
        # more tool call is the same mechanism it has been using all
        # along, and it does not depend on a provider feature that
        # behaves differently across models.
        response_format=ToolStrategy(CAPABILITY_SCHEMAS[capability]),
        name=f"household-{capability}",
    )


async def run(
    snapshot: HouseholdSnapshot,
    capability: str,
    *,
    month: Optional[str] = None,
    question: Optional[str] = None,
    horizon_days: int = 45,
    history: Optional[Sequence[tuple[str, str]]] = None,
) -> AgentResult:
    """Run one capability against one household and return its structured
    answer.

    `history` is only meaningful for `ask`: it is the earlier turns of a
    chat, oldest first. This service holds no conversation state, so a
    caller that wants follow-up questions to work sends what was said
    before.
    """
    if not settings.llm_configured:
        raise LLMNotConfigured(
            "No Ollama host is configured (OLLAMA_BASE_URL). The /analysis "
            "endpoints still work without it."
        )

    agent = build_agent(snapshot, capability)
    replayed = list(history or []) if capability == "ask" else []
    task = _task_prompt(
        capability,
        month=month,
        question=question,
        horizon_days=horizon_days,
        has_history=bool(replayed),
    )

    started = time.perf_counter()
    try:
        state = await asyncio.wait_for(
            agent.ainvoke(
                {"messages": _conversation(task, replayed)},
                config={"recursion_limit": settings.recursion_limit},
            ),
            timeout=settings.timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        raise AgentTimeout(
            f"The {capability} analysis took longer than "
            f"{settings.timeout_seconds}s and was stopped."
        ) from exc
    except GraphRecursionError as exc:
        # The genuine article: the graph looped until it ran out of
        # steps. Named separately from the generic failure because the
        # remedy is specific and the opposite of the obvious one —
        # raising the limit buys more of the same loop, so the thing to
        # look at is the tool-call list for a repeat.
        raise AgentError(
            f"The {capability} analysis looped until it hit the "
            f"{settings.recursion_limit}-step limit without producing an "
            f"answer. Raising the limit will not help: check whether the "
            f"model is repeating one tool call."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as 502
        log.exception("agent run failed: capability=%s", capability)
        raise AgentError(f"The {capability} analysis failed: {exc}") from exc

    messages = state.get("messages", [])
    structured = state.get("structured_response")
    calls = _tool_calls(messages)

    # Evidence is the load-bearing check, and it runs before anything
    # else: an answer assembled without consulting the books is not an
    # answer, however well it validates. A small model will occasionally
    # call the response tool straight away and fill it from the prompt
    # alone — producing, in one observed run, a confident "no monthly
    # budget is set" for a household whose budget is 80,000. The schema
    # cannot catch that: the shape is perfect and only the content is
    # invented. Delegating capabilities are covered too, because `task`
    # is listed as non-evidence — a subagent's findings reach the main
    # agent as prose, so a parent that only delegated has nothing sourced.
    schema_name = CAPABILITY_SCHEMAS[capability].__name__
    evidence = [c for c in calls if c != schema_name and c not in _NON_EVIDENCE_TOOLS]
    if not evidence:
        raise AgentError(
            f"The {capability} analysis called the output tool without reading "
            f"the household's books first, so every figure in it would be "
            f"invented. Tool calls: {', '.join(calls) or 'none'}."
        )

    finished_by_fallback = False
    if structured is None:
        # The model read the books and then wrote its answer as ordinary
        # prose instead of submitting it through the output tool. The
        # work is done; only the envelope is missing. Rather than throw
        # a completed analysis away, re-ask for just the envelope — see
        # `_finish`. This only runs because `evidence` is non-empty, so
        # the fallback always has real tool output to draw on.
        structured = await _finish(capability, messages, started)
        finished_by_fallback = structured is not None

    if structured is None:
        turns = sum(1 for m in messages if isinstance(m, AIMessage))
        raise AgentError(
            f"The {capability} analysis ended after {turns} model turn(s) "
            f"without calling the output tool, and could not be re-stated as "
            f"one either. Tools it called: {', '.join(calls) or 'none'}. "
            f"(The {settings.recursion_limit}-step limit was not reached.)"
        )

    duration_ms = int((time.perf_counter() - started) * 1000)

    payload = (
        structured.model_dump(by_alias=True)
        if hasattr(structured, "model_dump")
        else dict(structured)
    )

    # Last gate: the figures have to actually be in the answer. A model
    # can call every right tool, satisfy the schema, and still hand back
    # a template it never filled in.
    if (holes := _placeholders(payload)):
        raise AgentError(
            f"The {capability} analysis came back with placeholders where the "
            f"figures should be ({', '.join(holes[:3])}) — the model described "
            f"where the numbers would come from instead of copying them."
        )
    return AgentResult(
        capability=capability,
        result=payload,
        model=settings.agent_model,
        tool_calls=calls,
        steps=len(messages),
        duration_ms=duration_ms,
        truncated=len(calls) >= settings.recursion_limit - 1,
        restated=finished_by_fallback,
    )
