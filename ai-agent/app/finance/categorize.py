"""Capability 1 — automatically categorise expenses.

A two-pass design, and the split is the whole point:

1. **Rules.** `app/finance/rules.py` resolves the merchants a household
   actually repeats. Free, instant, and identical every time it runs.
2. **History.** If this household has categorised "Sharma Kirana Store"
   before, that is better evidence than any table — it is *their* answer
   for *their* merchant. History is checked first for exactly that
   reason.
3. **The model.** Only what neither pass resolved reaches the LLM, with
   the household's own category list to choose from.

Nothing here writes. The service returns *suggestions* with a confidence
and the reason they were made; applying them is the backend's call,
which keeps the agent read-only and keeps the user in the loop on a
change to their own books.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

from app.data.models import TYPE_EXPENSE, Transaction
from app.data.snapshot import HouseholdSnapshot
from app.finance.rules import match_category_name

# Below this, a suggestion is offered but flagged for review rather than
# presented as settled.
CONFIDENT = 0.8
# A household's own past choice needs this many prior examples before it
# outranks the merchant table.
HISTORY_MIN_EXAMPLES = 2


@dataclass(frozen=True)
class Suggestion:
    transaction_id: int
    date: str
    name: str
    merchant: str
    amount: float
    category_id: int
    category_name: str
    confidence: float
    # "history" | "rules" — how it was decided. Surfaced so a user who
    # disagrees can tell a table match from their own precedent.
    source: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "transactionId": self.transaction_id,
            "date": self.date,
            "name": self.name,
            "merchant": self.merchant,
            "amount": round(self.amount, 2),
            "categoryId": self.category_id,
            "categoryName": self.category_name,
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "reason": self.reason,
            "needsReview": self.confidence < CONFIDENT,
        }


def _key(txn: Transaction) -> str:
    """What identifies 'the same payee again'. Merchant when the user
    filled it in, else the transaction name."""
    return ((txn.merchant or txn.name or "").strip().casefold())


def learned_merchant_map(snapshot: HouseholdSnapshot) -> dict[str, tuple[int, int]]:
    """merchant key -> (most-used category id, how many times).

    Built only from rows the household categorised itself, so it encodes
    their preferences rather than ours.
    """
    seen: dict[str, Counter] = defaultdict(Counter)
    for txn in snapshot.transactions:
        if txn.category_id is None:
            continue
        key = _key(txn)
        if key:
            seen[key][txn.category_id] += 1
    resolved: dict[str, tuple[int, int]] = {}
    for key, counts in seen.items():
        category_id, hits = counts.most_common(1)[0]
        resolved[key] = (category_id, hits)
    return resolved


def uncategorised(snapshot: HouseholdSnapshot, limit: Optional[int] = None) -> list[Transaction]:
    """Expense rows with no category, newest first — the newest are the
    ones a user is most likely to still remember."""
    rows = [
        t
        for t in snapshot.transactions
        if t.type == TYPE_EXPENSE and t.category_id is None
    ]
    rows.sort(key=lambda t: ((t.date or ""), t.id or 0), reverse=True)
    return rows[:limit] if limit else rows


def suggest(
    snapshot: HouseholdSnapshot, limit: Optional[int] = None
) -> tuple[list[Suggestion], list[Transaction]]:
    """Returns (what the deterministic passes resolved, what is left for
    the model)."""
    history = learned_merchant_map(snapshot)
    resolved: list[Suggestion] = []
    unresolved: list[Transaction] = []

    for txn in uncategorised(snapshot, limit):
        key = _key(txn)
        prior = history.get(key)
        if prior and prior[1] >= HISTORY_MIN_EXAMPLES:
            category_id, hits = prior
            resolved.append(
                Suggestion(
                    transaction_id=txn.id or 0,
                    date=txn.date,
                    name=txn.name,
                    merchant=txn.merchant,
                    amount=float(txn.amount or 0),
                    category_id=category_id,
                    category_name=snapshot.category_name(category_id),
                    # More precedent, more confidence, capped short of
                    # certainty — the household can always be wrong too.
                    confidence=min(0.97, 0.80 + 0.04 * hits),
                    source="history",
                    reason=(
                        f"You have categorised '{txn.merchant or txn.name}' as "
                        f"{snapshot.category_name(category_id)} {hits} time(s) before"
                    ),
                )
            )
            continue

        matched = match_category_name([txn.merchant, txn.name])
        if matched:
            category_name, token = matched
            category_id = snapshot.category_id_for(category_name)
            # A household that renamed or deleted the category the rule
            # points at simply falls through to the model.
            if category_id is not None:
                resolved.append(
                    Suggestion(
                        transaction_id=txn.id or 0,
                        date=txn.date,
                        name=txn.name,
                        merchant=txn.merchant,
                        amount=float(txn.amount or 0),
                        category_id=category_id,
                        category_name=category_name,
                        confidence=0.85,
                        source="rules",
                        reason=f"'{token}' is a known {category_name} merchant",
                    )
                )
                continue

        unresolved.append(txn)

    return resolved, unresolved


def coverage(snapshot: HouseholdSnapshot) -> dict:
    """How much of the ledger is categorised at all. The number that says
    whether any category-based analysis can be trusted yet."""
    expenses = [t for t in snapshot.transactions if t.type == TYPE_EXPENSE]
    total = len(expenses)
    done = sum(1 for t in expenses if t.category_id is not None)
    return {
        "totalExpenses": total,
        "categorised": done,
        "uncategorised": total - done,
        "coveragePct": round(done / total * 100, 1) if total else 0.0,
    }
