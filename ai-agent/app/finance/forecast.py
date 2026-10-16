"""Capability 4 — forecast next month's expenses.

A single trailing average is the obvious forecast and the wrong one. A
household's outflow is two different things stacked on top of each
other, and they behave nothing alike:

- **Committed** money — rent, EMIs, SIPs, insurance, subscriptions. This
  is knowable, not predictable: the amount and the date are already
  decided. It is taken from the detected recurring payments plus the EMI
  and SIP figures the user entered, never from an average.
- **Variable** money — groceries, eating out, fuel, shopping. This is
  where a statistic belongs, and it is estimated per category from the
  trailing median of spend *after* the committed rows are removed, so a
  category containing both (utilities: a fixed broadband bill and a
  variable power bill) does not get its subscription counted twice.

The median is used rather than the mean for the reason it is used
everywhere else here: with six months of history one holiday is enough to
drag a mean up permanently.

A **trend** term nudges the estimate when the last three months are
consistently above or below the older ones, damped to half the observed
drift — a household that has been creeping up for three months will
probably keep creeping, but rarely as fast as the naive extrapolation
says.

The range matters more than the point estimate, so every forecast
carries a low/high band from the historical dispersion, and a confidence
that falls when there is little history or a lot of scatter.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Sequence

from app.data.models import (
    RECURRING_INVESTMENT_KINDS,
    TYPE_EXPENSE,
    Transaction,
)
from app.data.snapshot import HouseholdSnapshot
from app.finance.month import (
    in_month,
    mad,
    median,
    month_key,
    month_label,
    next_month_key,
    recent_month_keys,
    this_month_key,
    totals_for,
)
from app.finance.naming import suffixed
from app.finance.recurring import Recurring, covered_by_record, record_names
from app.finance.recurring import detect as detect_recurring

LOOKBACK_MONTHS = 6
# Under this many months of history, a forecast is a guess with a decimal
# point on it. It is still returned — a new user should see something —
# but flagged low confidence and said plainly in `basis`.
MIN_HISTORY_MONTHS = 3
# Only half of an observed drift is carried forward. See the docstring.
TREND_DAMPING = 0.5
# A single month may not move the trend term by more than this share of
# the base, which keeps one outlier from dominating.
MAX_TREND_ADJUSTMENT = 0.20


@dataclass(frozen=True)
class CategoryForecast:
    category_id: Optional[int]
    category_name: str
    committed: float
    variable: float
    expected: float
    low: float
    high: float
    history: list[float]
    trend_pct: Optional[float]

    def as_dict(self) -> dict:
        return {
            "categoryId": self.category_id,
            "categoryName": self.category_name,
            "committed": round(self.committed, 2),
            "variable": round(self.variable, 2),
            "expected": round(self.expected, 2),
            "low": round(self.low, 2),
            "high": round(self.high, 2),
            "recentMonths": [round(v, 2) for v in self.history],
            "trendPct": self.trend_pct,
        }


@dataclass(frozen=True)
class Forecast:
    month: str
    label: str
    expected: float
    low: float
    high: float
    committed: float
    variable: float
    confidence: str  # high | medium | low
    basis: str
    months_of_history: int
    expected_income: float
    expected_surplus: float
    categories: list[CategoryForecast]
    committed_items: list[dict]

    def as_dict(self) -> dict:
        return {
            "month": self.month,
            "label": self.label,
            "expected": round(self.expected, 2),
            "low": round(self.low, 2),
            "high": round(self.high, 2),
            "committed": round(self.committed, 2),
            "variable": round(self.variable, 2),
            "confidence": self.confidence,
            "basis": self.basis,
            "monthsOfHistory": self.months_of_history,
            "expectedIncome": round(self.expected_income, 2),
            "expectedSurplus": round(self.expected_surplus, 2),
            "categories": [c.as_dict() for c in self.categories],
            "committedItems": self.committed_items,
        }


def _trend_multiplier(history: Sequence[float]) -> tuple[float, Optional[float]]:
    """Compare the recent half of the history to the older half.

    Returns (multiplier, observed drift %), and `None` for the drift
    whenever it would not mean anything: fewer than four months, or a
    series with too many empty months. A category that saw spend in two
    of six months produces drifts like -100% out of nothing but
    sparseness, and a number that precise deserves to be withheld rather
    than damped.
    """
    if len(history) < 4:
        return 1.0, None
    if sum(1 for v in history if v > 0) < len(history) - 1:
        return 1.0, None
    split = len(history) // 2
    older, newer = median(history[:split]), median(history[split:])
    if older <= 0:
        return 1.0, None
    drift = (newer - older) / older
    damped = max(-MAX_TREND_ADJUSTMENT, min(MAX_TREND_ADJUSTMENT, drift * TREND_DAMPING))
    return 1.0 + damped, round(drift * 100, 1)


def _committed_by_category(
    snapshot: HouseholdSnapshot, recurrings: Sequence[Recurring]
) -> tuple[dict[Optional[int], float], list[dict]]:
    """Everything already decided about next month, and where it lands.

    The three sources overlap — a linked EMI is both a row in the ledger
    and a field on a loan — so the loan and holding records win and the
    matching ledger pattern is dropped. Counting both is how a forecast
    quietly gains an extra EMI.
    """
    by_category: dict[Optional[int], float] = defaultdict(float)
    items: list[dict] = []
    names = record_names(snapshot)

    for item in recurrings:
        if not item.active:
            continue
        # Loan and investment rows are not category spend in this app's
        # model, and their amounts arrive below from the record itself.
        if covered_by_record(item, names):
            continue
        by_category[item.category_id] += item.typical_amount
        items.append(
            {
                "label": item.label,
                "amount": round(item.typical_amount, 2),
                "kind": "recurring",
                "categoryName": item.category_name,
                "dayOfMonth": item.typical_day,
            }
        )

    # EMIs and SIPs come from what the user entered about the product,
    # which is better evidence than a pattern inferred from the ledger.
    # They are listed separately rather than added to a category, because
    # neither is category spend in this app's model: a loan payment is a
    # Loan row and an SIP is an Investment row.
    for debt in snapshot.debts:
        emi = float(debt.emi or 0)
        if emi > 0 and float(debt.outstanding or 0) > 0:
            items.append(
                {
                    "label": suffixed(debt.name, "EMI"),
                    "amount": round(emi, 2),
                    "kind": "emi",
                    "categoryName": "Loan payment",
                    "dayOfMonth": None,
                }
            )

    for holding in snapshot.investments:
        contribution = float(holding.monthly_contribution or 0)
        if contribution > 0 and holding.kind in RECURRING_INVESTMENT_KINDS:
            items.append(
                {
                    "label": suffixed(holding.name, holding.kind.upper()),
                    "amount": round(contribution, 2),
                    "kind": "investment",
                    "categoryName": "Investment",
                    "dayOfMonth": None,
                }
            )

    return by_category, items


def _variable_history(
    snapshot: HouseholdSnapshot,
    months: Sequence[str],
    committed_keys: set[str],
) -> dict[Optional[int], list[float]]:
    """Per category, the non-committed expense total for each month in
    the window. Committed payees are excluded so they are not counted
    once as a commitment and again inside the average."""
    history: dict[Optional[int], list[float]] = defaultdict(lambda: [0.0] * len(months))
    index = {mk: i for i, mk in enumerate(months)}

    def payee(txn: Transaction) -> str:
        return (txn.merchant or txn.name or "").strip().casefold()

    for txn in snapshot.transactions:
        if txn.type != TYPE_EXPENSE:
            continue
        slot = index.get(month_key(txn.date))
        if slot is None or payee(txn) in committed_keys:
            continue
        history[txn.category_id][slot] += float(txn.amount or 0)
    return history


def forecast(snapshot: HouseholdSnapshot, mk: Optional[str] = None) -> Forecast:
    """Forecast the month after `mk` (default: the month after this one)."""
    current = mk or this_month_key(snapshot.as_of)
    target = next_month_key(current)

    # The window ends at the month *before* `current`: a month still in
    # progress is a partial total and would drag every median down.
    window = recent_month_keys(current, LOOKBACK_MONTHS + 1)[:-1]
    available = [m for m in window if in_month(snapshot.transactions, m)]
    months_of_history = len(available)

    recurrings = detect_recurring(snapshot, current)
    committed_by_category, committed_items = _committed_by_category(snapshot, recurrings)
    committed_keys = {r.key for r in recurrings if r.active}
    committed_total = sum(float(i["amount"]) for i in committed_items)

    variable_history = _variable_history(snapshot, window, committed_keys)

    categories: list[CategoryForecast] = []
    variable_total = 0.0
    for category_id, series in variable_history.items():
        observed = [v for v, mkey in zip(series, window) if mkey in available]
        if not observed or max(observed) <= 0:
            continue
        base = median(observed)
        multiplier, drift = _trend_multiplier(observed)
        expected = base * multiplier
        # The band is the historical scatter, floored at 10% so a
        # coincidentally steady category does not claim false precision.
        spread = max(mad(observed), base * 0.10)
        committed_here = committed_by_category.get(category_id, 0.0)
        variable_total += expected
        categories.append(
            CategoryForecast(
                category_id=category_id,
                category_name=snapshot.category_name(category_id),
                committed=committed_here,
                variable=expected,
                expected=expected + committed_here,
                low=max(0.0, expected - spread) + committed_here,
                high=expected + spread + committed_here,
                history=observed,
                trend_pct=drift,
            )
        )
    categories.sort(key=lambda c: -c.expected)

    # The whole-month band is taken from the scatter of whole-month
    # totals, not from summing the per-category bands — categories do not
    # all peak in the same month, so adding their extremes would give an
    # absurdly wide range.
    month_totals = [totals_for(snapshot.transactions, m).spend for m in available]
    total_spread = max(mad(month_totals), median(month_totals) * 0.08) if month_totals else 0.0

    expected_total = committed_total + variable_total
    expected_income = snapshot.recurring_monthly_income

    if months_of_history >= LOOKBACK_MONTHS:
        confidence = "high"
    elif months_of_history >= MIN_HISTORY_MONTHS:
        confidence = "medium"
    else:
        confidence = "low"
    # A forecast that is mostly commitments is trustworthy even on thin
    # history, because most of it is not being predicted at all.
    if confidence != "high" and expected_total > 0 and committed_total / expected_total > 0.6:
        confidence = "medium" if confidence == "low" else confidence

    if months_of_history == 0:
        basis = (
            "No completed months of spending yet, so this is built entirely from "
            "standing commitments (EMIs, SIPs and detected recurring payments)."
        )
    else:
        basis = (
            f"{months_of_history} completed month(s) of history. "
            f"₹{committed_total:,.0f} is already committed "
            f"({len(committed_items)} standing payments); the remaining "
            f"₹{variable_total:,.0f} is the trailing median of variable spend per "
            f"category, trend-adjusted."
        )

    return Forecast(
        month=target,
        label=month_label(target),
        expected=expected_total,
        low=max(0.0, expected_total - total_spread),
        high=expected_total + total_spread,
        committed=committed_total,
        variable=variable_total,
        confidence=confidence,
        basis=basis,
        months_of_history=months_of_history,
        expected_income=expected_income,
        expected_surplus=expected_income - expected_total,
        categories=categories,
        committed_items=sorted(committed_items, key=lambda i: -float(i["amount"])),
    )
