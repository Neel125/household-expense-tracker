"""Capability 2 — detect unusual spending.

"Unusual" has to mean unusual *for this household*. A ₹40,000 month is
alarming for one family and a Tuesday for another, so every test here
compares a household against its own recent history and never against an
absolute threshold.

The statistic is a **modified z-score** built on the median and the
median absolute deviation rather than mean and standard deviation. With
six or eight months of history, one genuine one-off — a wedding, an
annual insurance premium — moves a mean and inflates a standard
deviation enough that the threshold meant to catch the *next* outlier no
longer does. The median does not move, which is exactly the property
wanted from a detector.

Six checks run, each answering a different way spending goes wrong:

- a category costing far more this month than it usually does;
- one transaction far larger than that category's usual transaction;
- a first-time payee taking a large amount;
- many more charges from one payee than normal;
- the same amount to the same payee twice in a few days (a double charge);
- a standing commitment that did not arrive (a failed payment, or a
  subscription the user forgot they cancelled).

Every finding carries the numbers it was derived from, so the model
narrating it cannot invent a different figure.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Sequence

from app.data.models import TYPE_EXPENSE, Transaction
from app.data.snapshot import HouseholdSnapshot
from app.finance.month import (
    in_month,
    mad,
    median,
    month_key,
    month_label,
    parse_date,
    recent_month_keys,
    this_month_key,
)
from app.finance.recurring import detect as detect_recurring

# 0.6745 is the constant that puts a MAD-based score on the same scale as
# a standard z-score, so "3" means what a reader expects it to mean.
_MAD_TO_SIGMA = 0.6745

LOOKBACK_MONTHS = 6
# Below this many prior months there is no baseline worth testing against,
# and firing anyway would just alarm every new user.
MIN_HISTORY_MONTHS = 3
SPIKE_SCORE = 3.0
LARGE_TXN_SCORE = 3.5
# Absolute floors. Without these, a household that normally spends ₹80 on
# something gets an "anomaly" for spending ₹300, which is noise.
MIN_CATEGORY_SPIKE = 1000.0
MIN_TRANSACTION_AMOUNT = 1000.0
MIN_NEW_MERCHANT_AMOUNT = 2500.0
DUPLICATE_WINDOW_DAYS = 3

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass(frozen=True)
class Anomaly:
    kind: str
    severity: str
    title: str
    detail: str
    amount: float
    # What the same thing normally costs, so the gap is always visible.
    baseline: float
    score: Optional[float]
    month: str
    category_name: str = ""
    merchant: str = ""
    transaction_ids: tuple[int, ...] = ()

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "amount": round(self.amount, 2),
            "baseline": round(self.baseline, 2),
            "excess": round(self.amount - self.baseline, 2),
            "score": round(self.score, 2) if self.score is not None else None,
            "month": self.month,
            "categoryName": self.category_name,
            "merchant": self.merchant,
            "transactionIds": list(self.transaction_ids),
        }


def modified_z(value: float, history: Sequence[float]) -> Optional[float]:
    """How many robust sigmas `value` sits above the history's median.

    None when there is nothing to compare against. When the spread is
    genuinely zero — a household paying the identical rent every month —
    MAD is 0 and the usual formula divides by zero; a 25% band around the
    median stands in, so a rent rise still registers without the score
    exploding to infinity.
    """
    if len(history) < MIN_HISTORY_MONTHS:
        return None
    centre = median(history)
    spread = mad(history)
    if spread <= 0:
        spread = abs(centre) * 0.25
    if spread <= 0:
        return None
    return _MAD_TO_SIGMA * (value - centre) / spread


def _severity(score: Optional[float], excess: float) -> str:
    """Both halves matter: a huge relative jump on a trivial amount is
    low priority, and so is a small relative jump on a huge amount."""
    if score is not None and score >= 5 and excess >= 5000:
        return "high"
    if (score is not None and score >= 4) or excess >= 10000:
        return "high"
    if (score is not None and score >= 3) or excess >= 3000:
        return "medium"
    return "low"


def _payee(txn: Transaction) -> str:
    return (txn.merchant or txn.name or "").strip()


# ------------------------------------------------------------- the checks
def _category_spikes(
    snapshot: HouseholdSnapshot, mk: str, history_keys: Sequence[str]
) -> list[Anomaly]:
    found: list[Anomaly] = []
    current = in_month(snapshot.transactions, mk)

    by_category_now: dict[Optional[int], float] = defaultdict(float)
    for txn in current:
        if txn.type == TYPE_EXPENSE:
            by_category_now[txn.category_id] += float(txn.amount or 0)

    for category_id, amount in by_category_now.items():
        history = []
        for key in history_keys:
            total = sum(
                float(t.amount or 0)
                for t in in_month(snapshot.transactions, key)
                if t.type == TYPE_EXPENSE and t.category_id == category_id
            )
            history.append(total)

        score = modified_z(amount, history)
        baseline = median(history)
        excess = amount - baseline
        if score is None or score < SPIKE_SCORE or excess < MIN_CATEGORY_SPIKE:
            continue
        name = snapshot.category_name(category_id)
        found.append(
            Anomaly(
                kind="category_spike",
                severity=_severity(score, excess),
                title=f"{name} is well above its usual level",
                detail=(
                    f"{name} came to ₹{amount:,.0f} in {month_label(mk)} against a "
                    f"usual ₹{baseline:,.0f} over the previous {len(history)} months "
                    f"— ₹{excess:,.0f} more than normal."
                ),
                amount=amount,
                baseline=baseline,
                score=score,
                month=mk,
                category_name=name,
            )
        )
    return found


def _large_transactions(
    snapshot: HouseholdSnapshot, mk: str, history_keys: Sequence[str]
) -> list[Anomaly]:
    """One row that dwarfs what this category's rows normally cost."""
    past_by_category: dict[Optional[int], list[float]] = defaultdict(list)
    window = set(history_keys)
    for txn in snapshot.transactions:
        if txn.type == TYPE_EXPENSE and month_key(txn.date) in window:
            past_by_category[txn.category_id].append(float(txn.amount or 0))

    found: list[Anomaly] = []
    for txn in in_month(snapshot.transactions, mk):
        if txn.type != TYPE_EXPENSE:
            continue
        amount = float(txn.amount or 0)
        if amount < MIN_TRANSACTION_AMOUNT:
            continue
        history = past_by_category.get(txn.category_id, [])
        # Enough *transactions*, not months, is the right bar here.
        if len(history) < 5:
            continue
        score = modified_z(amount, history)
        baseline = median(history)
        if score is None or score < LARGE_TXN_SCORE:
            continue
        name = snapshot.category_name(txn.category_id)
        found.append(
            Anomaly(
                kind="large_transaction",
                severity=_severity(score, amount - baseline),
                title=f"Unusually large {name} charge",
                detail=(
                    f"₹{amount:,.0f} to {_payee(txn) or 'an unnamed payee'} on "
                    f"{txn.date}. A typical {name} charge is ₹{baseline:,.0f}."
                ),
                amount=amount,
                baseline=baseline,
                score=score,
                month=mk,
                category_name=name,
                merchant=_payee(txn),
                transaction_ids=(txn.id or 0,),
            )
        )
    return found


def _new_large_payees(
    snapshot: HouseholdSnapshot, mk: str, history_keys: Sequence[str]
) -> list[Anomaly]:
    window = set(history_keys)
    known = {
        _payee(t).casefold()
        for t in snapshot.transactions
        if month_key(t.date) in window and _payee(t)
    }

    found: list[Anomaly] = []
    for txn in in_month(snapshot.transactions, mk):
        if txn.type != TYPE_EXPENSE:
            continue
        payee = _payee(txn)
        amount = float(txn.amount or 0)
        if not payee or payee.casefold() in known or amount < MIN_NEW_MERCHANT_AMOUNT:
            continue
        found.append(
            Anomaly(
                kind="new_large_payee",
                severity="high" if amount >= 10000 else "medium",
                title=f"First payment to {payee}",
                detail=(
                    f"₹{amount:,.0f} on {txn.date} to {payee}, which does not appear "
                    f"anywhere in the previous {len(history_keys)} months."
                ),
                amount=amount,
                baseline=0.0,
                score=None,
                month=mk,
                category_name=snapshot.category_name(txn.category_id),
                merchant=payee,
                transaction_ids=(txn.id or 0,),
            )
        )
    return found


def _frequency_spikes(
    snapshot: HouseholdSnapshot, mk: str, history_keys: Sequence[str]
) -> list[Anomaly]:
    """Same payee, far more often than usual — the shape of a habit
    forming, which a total alone can hide."""
    counts_now: dict[str, list[Transaction]] = defaultdict(list)
    for txn in in_month(snapshot.transactions, mk):
        if txn.type == TYPE_EXPENSE and _payee(txn):
            counts_now[_payee(txn).casefold()].append(txn)

    found: list[Anomaly] = []
    for key, rows in counts_now.items():
        if len(rows) < 4:
            continue
        history = []
        for month in history_keys:
            history.append(
                sum(
                    1
                    for t in in_month(snapshot.transactions, month)
                    if t.type == TYPE_EXPENSE and _payee(t).casefold() == key
                )
            )
        score = modified_z(len(rows), history)
        baseline = median(history)
        if score is None or score < SPIKE_SCORE or len(rows) - baseline < 3:
            continue
        spent = sum(float(t.amount or 0) for t in rows)
        payee = _payee(rows[0])
        found.append(
            Anomaly(
                kind="frequency_spike",
                severity=_severity(score, spent),
                title=f"{payee} far more often than usual",
                detail=(
                    f"{len(rows)} charges totalling ₹{spent:,.0f} in {month_label(mk)}, "
                    f"against a usual {baseline:.0f} a month."
                ),
                amount=spent,
                baseline=baseline,
                score=score,
                month=mk,
                category_name=snapshot.category_name(rows[0].category_id),
                merchant=payee,
                transaction_ids=tuple(t.id or 0 for t in rows),
            )
        )
    return found


def _duplicates(snapshot: HouseholdSnapshot, mk: str) -> list[Anomaly]:
    """The same amount to the same payee within a few days. Usually a
    double charge or a row logged twice; occasionally genuine, which is
    why it is reported rather than acted on."""
    grouped: dict[tuple[str, float], list[Transaction]] = defaultdict(list)
    for txn in in_month(snapshot.transactions, mk):
        if txn.type != TYPE_EXPENSE:
            continue
        payee = _payee(txn).casefold()
        amount = round(float(txn.amount or 0), 2)
        if payee and amount > 0:
            grouped[(payee, amount)].append(txn)

    found: list[Anomaly] = []
    for (_, amount), rows in grouped.items():
        if len(rows) < 2:
            continue
        rows.sort(key=lambda t: (t.date or ""))
        for first, second in zip(rows, rows[1:]):
            a, b = parse_date(first.date), parse_date(second.date)
            if a is None or b is None or (b - a).days > DUPLICATE_WINDOW_DAYS:
                continue
            payee = _payee(first)
            found.append(
                Anomaly(
                    kind="possible_duplicate",
                    severity="medium" if amount >= 1000 else "low",
                    title=f"Possible duplicate charge from {payee}",
                    detail=(
                        f"₹{amount:,.0f} to {payee} on both {first.date} and "
                        f"{second.date}. Worth checking whether it was billed twice."
                    ),
                    amount=amount,
                    baseline=amount,
                    score=None,
                    month=mk,
                    category_name=snapshot.category_name(first.category_id),
                    merchant=payee,
                    transaction_ids=(first.id or 0, second.id or 0),
                )
            )
    return found


def _missing_recurring(snapshot: HouseholdSnapshot, mk: str) -> list[Anomaly]:
    """A standing commitment that did not show up this month. Only
    reported once the day it usually falls on has passed, so a rent
    payment due on the 5th is not 'missing' on the 2nd."""
    if mk != this_month_key(snapshot.as_of):
        return []

    paid_keys = {
        (t.merchant or t.name or "").strip().casefold()
        for t in in_month(snapshot.transactions, mk)
    }
    found: list[Anomaly] = []
    for item in detect_recurring(snapshot, mk):
        if not item.active or item.key in paid_keys:
            continue
        if snapshot.as_of.day <= item.typical_day:
            continue
        found.append(
            Anomaly(
                kind="missing_recurring",
                severity="medium" if item.typical_amount >= 1000 else "low",
                title=f"{item.label} has not been paid this month",
                detail=(
                    f"{item.label} normally costs ₹{item.typical_amount:,.0f} around the "
                    f"{item.typical_day}th and has been paid in {len(item.months_seen)} of "
                    f"the last months, but there is no entry for {month_label(mk)}. "
                    f"Either the payment failed, or it is logged under another name."
                ),
                amount=0.0,
                baseline=item.typical_amount,
                score=None,
                month=mk,
                category_name=item.category_name,
                merchant=item.label,
            )
        )
    return found


# ------------------------------------------------------------------ entry
def detect(snapshot: HouseholdSnapshot, mk: Optional[str] = None) -> list[Anomaly]:
    """Every check, most serious first."""
    mk = mk or this_month_key(snapshot.as_of)
    history_keys = recent_month_keys(mk, LOOKBACK_MONTHS + 1)[:-1]

    found = (
        _category_spikes(snapshot, mk, history_keys)
        + _large_transactions(snapshot, mk, history_keys)
        + _new_large_payees(snapshot, mk, history_keys)
        + _frequency_spikes(snapshot, mk, history_keys)
        + _duplicates(snapshot, mk)
        + _missing_recurring(snapshot, mk)
    )
    found.sort(
        key=lambda a: (SEVERITY_ORDER.get(a.severity, 9), -(a.amount - a.baseline))
    )
    return found
