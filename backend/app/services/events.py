"""A tiny in-process domain event bus.

The rewards layer is deliberately *not* called directly from the expense,
budget or goal services: those publish a fact about the domain
("EXPENSE_TRACKED") and stay ignorant of who listens. That keeps the
dependency pointing one way — rewards knows about expenses, expenses know
nothing about rewards — so the whole reward system can be removed, or
moved behind a real broker (Kafka, SQS, an outbox table), by replacing
this module alone. Handlers are registered once at startup in
app.main:create_app.

Dispatch is synchronous and shares the caller's session, which is what a
single-process, self-hosted app wants: a coin lands in the same
transaction boundary as the expense that earned it. A handler that raises
is logged and skipped — a reward bug must never fail a user's save.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlmodel import Session

log = logging.getLogger(__name__)

# ------------------------------------------------------------- event names
EXPENSE_TRACKED = "EXPENSE_TRACKED"
EXPENSE_DELETED = "EXPENSE_DELETED"
GOAL_COMPLETED = "GOAL_COMPLETED"
# Investments earn a small coin on being tracked and a larger one when
# they reach maturity — the same "reward the discipline, not the size"
# principle the rest of the catalogue follows.
INVESTMENT_ADDED = "INVESTMENT_ADDED"
INVESTMENT_DELETED = "INVESTMENT_DELETED"
INVESTMENT_MATURED = "INVESTMENT_MATURED"
# Fired when an outstanding loan drops to zero. Payload carries the debt
# kind so the handler can pick the right coin tier (home vs car vs other).
DEBT_COMPLETED = "DEBT_COMPLETED"


@dataclass
class DomainEvent:
    name: str
    household_id: int
    user_id: int | None = None
    payload: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[Session, DomainEvent], None]

_subscribers: dict[str, list[Handler]] = {}


def subscribe(name: str, handler: Handler) -> None:
    _subscribers.setdefault(name, []).append(handler)


def clear() -> None:
    """Drop every subscription — for tests, and so a re-run of the startup
    wiring can't register the same handler twice."""
    _subscribers.clear()


def publish(session: Session, event: DomainEvent) -> None:
    for handler in _subscribers.get(event.name, []):
        try:
            handler(session, event)
        except Exception:  # noqa: BLE001 - a listener must not break the write
            log.exception("Event handler failed for %s", event.name)
