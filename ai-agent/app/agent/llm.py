"""The chat model, and the harness the deep agent runs inside.

The model is **Ollama, running locally**. That is the whole point of the
choice: a household's ledger — every salary credit, every loan balance —
is read by a model on a machine the household controls, and nothing
monetary crosses a network boundary to a vendor. It also means a run
costs nothing but wall-clock, so the recursion limit here guards time
rather than a bill.

Three decisions are made here and nowhere else.

**Temperature is zero.** Two runs over the same unchanged books must not
disagree about whether the household is overspending. Variety is a
virtue in a writing assistant and a defect in a financial one.

**The context window is set explicitly.** Ollama defaults `num_ctx` to
2048 and then silently discards the oldest tokens when a prompt exceeds
it — which, for an agent carrying fifteen tool schemas and a few rounds
of tool output, means losing the system prompt rather than erroring.
`settings.num_ctx` is passed on every model built here.

**`execute` is removed, and so is the default general-purpose
subagent.** `create_deep_agent` offers a shell tool and auto-inserts a
catch-all subagent. This service has no sandbox and nothing to run, and
every fact it needs arrives through a typed finance tool. Disabling the
default subagent has a second effect worth having: with no subagents
passed, `task` is not exposed at all, so a narrow capability like
"check the budget" gets a small, fast tool surface and the three real
analysts appear only for the capabilities that delegate. Both are taken
away at the harness level rather than left present and discouraged in a
prompt.

The filesystem tools stay: they are a virtual, in-state scratchpad
(`StateBackend`), and they are what lets the report agent draft sections
across several subagent calls without carrying the whole draft in the
conversation.
"""
from __future__ import annotations

from functools import lru_cache

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.core.config import settings

_PROFILE_REGISTERED = False


def _register_profile() -> None:
    """Strip the shell tool and the catch-all subagent from every Ollama
    agent this process builds. Registration must happen before
    `create_deep_agent`, and is idempotent.

    The key is the provider name deepagents reads off the model instance
    (`ls_provider`), which `ChatOllama` reports as `"ollama"`."""
    global _PROFILE_REGISTERED
    if _PROFILE_REGISTERED:
        return
    from deepagents import (
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        register_harness_profile,
    )

    register_harness_profile(
        "ollama",
        HarnessProfile(
            excluded_tools=frozenset({"execute"}),
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    _PROFILE_REGISTERED = True


class LLMNotConfigured(RuntimeError):
    """Raised when a capability that needs the model is called without a
    reachable Ollama host, or with a model that is not pulled on it. The
    deterministic `/analysis/*` endpoints keep working, and the
    controller turns this into a 503 rather than a stack trace."""


# A generation may legitimately run for minutes on local hardware, but
# *opening the socket* should take milliseconds. One budget for both
# would mean a dead host hangs the request for the whole run timeout
# before admitting it is dead.
_CONNECT_TIMEOUT_SECONDS = 5.0


@lru_cache(maxsize=4)
def _build(model_name: str) -> BaseChatModel:
    _register_profile()
    try:
        return ChatOllama(
            model=model_name,
            base_url=settings.ollama_base_url,
            temperature=settings.temperature,
            num_ctx=settings.num_ctx,
            # With no API key to get wrong, the live misconfigurations are
            # a host that cannot be reached and a model that was never
            # pulled. Checking here turns both into one clear error at
            # construction, rather than something surfacing from inside
            # the agent loop half a minute later. `_build` is cached and
            # `lru_cache` does not cache exceptions, so this costs one
            # call per model per process and retries once you fix it.
            validate_model_on_init=True,
            client_kwargs={
                "timeout": httpx.Timeout(
                    settings.timeout_seconds, connect=_CONNECT_TIMEOUT_SECONDS
                )
            },
        )
    except ValueError as exc:
        # What `validate_model` raises: model not pulled, or a connection
        # error it recognised.
        raise LLMNotConfigured(f"{exc} (ollama at {settings.ollama_base_url})") from exc
    except httpx.HTTPError as exc:
        # What it does not: `validate_model` catches `ConnectError` but
        # not `ConnectTimeout`, which is the error you get when the host
        # is firewalled or Ollama is bound to loopback while this service
        # runs in a container. Without this, the transport error escapes
        # `build_agent`, misses the controller's error mapping entirely,
        # and the household gets a 500 with a traceback.
        raise LLMNotConfigured(
            f"Cannot reach ollama at {settings.ollama_base_url} "
            f"({type(exc).__name__}). If it runs on the host and this service "
            f"is in a container, the daemon must listen beyond loopback: "
            f"OLLAMA_HOST=0.0.0.0."
        ) from exc


def main_model() -> BaseChatModel:
    if not settings.llm_configured:
        raise LLMNotConfigured(
            "No Ollama host is configured (OLLAMA_BASE_URL). The deterministic "
            "/analysis endpoints still work; /agent endpoints need a model."
        )
    return _build(settings.agent_model)


def subagent_model() -> BaseChatModel:
    """Subagents get a model instance rather than a `"provider:name"`
    string. A string would be re-resolved by `init_chat_model` with no
    `base_url` and no `num_ctx` — so the analysts would quietly talk to
    localhost with a 2048-token window while the main agent talked to
    the configured host."""
    return _build(settings.subagent_model)
