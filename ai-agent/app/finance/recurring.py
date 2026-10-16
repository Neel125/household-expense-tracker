"""Finding the payments that repeat.

Subscriptions, rent, EMIs, SIPs, utility bills and insurance premiums are
most of a household's committed outflow, and none of them are labelled as
such in the ledger — the user just logs "Netflix" every month. Detecting
them is what lets the service forecast honestly (committed money is not a
guess) and warn about a bill before it lands.

The test a group has to pass is deliberately conservative, because a
false positive here becomes a bill the user is told to expect and a
forecast that is too high:

- it appears in at least `MIN_OCCURRENCES` distinct months;
- those months are recent — a subscription cancelled in March is not a
  commitment in September;
- the amounts are stable, measured as median absolute deviation against
  the median, so one price hike does not disqualify a real subscription
  but a payee whose amount is different every time is rejected.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Sequence

from app.data.models import (
    LOAN_PAYMENT_TYPES,
    NOT_SPEND,
    TYPE_INVESTMENT,
    Transaction,
)
from app.data.snapshot import HouseholdSnapshot
from app.finance.month import (
    mad,
    median,
    month_key,
    next_occurrence,
    parse_date,
    recent_month_keys,
    this_month_key,
)

# How far back to look for a repeating pattern.
LOOKBACK_MONTHS = 6
MIN_OCCURRENCES = 3
# Allowed spread in the amount, as a fraction of the median.
AMOUNT_TOLERANCE = 0.25
# A payee last seen more than this many months ago is treated as lapsed.
STALE_AFTER_MONTHS = 2

# Transaction types that are portfolio movements rather than household
# bills — see `Recurring.linked_to_portfolio`.
PORTFOLIO_TYPES = set(LOAN_PAYMENT_TYPES) | {TYPE_INVESTMENT}


@dataclass(frozen=True)
class Recurring:
    key: str
    label: str
    category_id: Optional[int]
    category_name: str
    typical_amount: float
    occurrences: int
    months_seen: list[str]
    first_seen: str
    last_seen: str
    typical_day: int
    next_due: str
    days_until: Optional[int]
    # True while it is still being paid; False once it looks cancelled.
    active: bool
    amount_stable: bool
    # True when these rows are EMIs or investment contributions. Such a
    # pattern is real, but it is the *same money* a Debt or Investment
    # record already describes, so callers that read both must not add
    # them together.
    linked_to_portfolio: bool = False

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "categoryName": self.category_name,
            "typicalAmount": round(self.typical_amount, 2),
            "occurrences": self.occurrences,
            "monthsSeen": self.months_seen,
            "firstSeen": self.first_seen,
            "lastSeen": self.last_seen,
            "typicalDayOfMonth": self.typical_day,
            "nextDue": self.next_due,
            "daysUntil": self.days_until,
            "active": self.active,
            "amountStable": self.amount_stable,
            "linkedToPortfolio": self.linked_to_portfolio,
        }


def _key(txn: Transaction) -> str:
    return (txn.merchant or txn.name or "").strip().casefold()


def _label(rows: Sequence[Transaction]) -> str:
    for row in reversed(rows):
        if row.merchant:
            return row.merchant
    return rows[-1].name if rows else ""


def detect(
    snapshot: HouseholdSnapshot,
    mk: Optional[str] = None,
    lookback: int = LOOKBACK_MONTHS,
) -> list[Recurring]:
    """Every payee that looks like a standing commitment, most imminent
    first."""
    mk = mk or this_month_key(snapshot.as_of)
    window = set(recent_month_keys(mk, lookback))

    grouped: dict[str, list[Transaction]] = defaultdict(list)
    for txn in snapshot.transactions:
        if txn.type in NOT_SPEND:
            continue
        if month_key(txn.date) not in window:
            continue
        key = _key(txn)
        if key:
            grouped[key].append(txn)

    found: list[Recurring] = []
    for key, rows in grouped.items():
        rows.sort(key=lambda t: ((t.date or ""), t.id or 0))
        months = sorted({month_key(r.date) for r in rows})
        if len(months) < MIN_OCCURRENCES:
            continue

        amounts = [float(r.amount or 0) for r in rows]
        centre = median(amounts)
        if centre <= 0:
            continue
        stable = mad(amounts) <= AMOUNT_TOLERANCE * centre
        if not stable:
            continue

        days = [parsed.day for r in rows if (parsed := parse_date(r.date))]
        typical_day = int(round(median(days))) if days else 1

        # Lapsed? Compare the last month it was seen against the window's
        # end rather than today, so an analysis run for a past month is
        # judged as of that month.
        gap = _months_between_keys(months[-1], mk)
        active = gap <= STALE_AFTER_MONTHS

        due = next_occurrence(typical_day, snapshot.as_of) if active else None
        categories = [r.category_id for r in rows if r.category_id is not None]
        category_id = max(set(categories), key=categories.count) if categories else None

        found.append(
            Recurring(
                key=key,
                label=_label(rows),
                category_id=category_id,
                category_name=snapshot.category_name(category_id),
                typical_amount=centre,
                occurrences=len(rows),
                months_seen=months,
                first_seen=rows[0].date,
                last_seen=rows[-1].date,
                typical_day=typical_day,
                next_due=due.isoformat() if due else "",
                days_until=(due - snapshot.as_of).days if due else None,
                active=active,
                amount_stable=stable,
                linked_to_portfolio=any(
                    r.type in PORTFOLIO_TYPES
                    or r.debt_id is not None
                    or r.investment_id is not None
                    for r in rows
                ),
            )
        )

    found.sort(key=lambda r: (r.days_until is None, r.days_until, -r.typical_amount))
    return found


def _months_between_keys(earlier: str, later: str) -> int:
    a = int(earlier[:4]) * 12 + int(earlier[5:7])
    b = int(later[:4]) * 12 + int(later[5:7])
    return b - a


def committed_monthly(recurrings: Sequence[Recurring]) -> float:
    """What the household owes every month before deciding anything."""
    return sum(r.typical_amount for r in recurrings if r.active)


def lapsed(recurrings: Sequence[Recurring]) -> list[Recurring]:
    """Subscriptions that stopped. Worth surfacing both ways: the user
    either cancelled it (and can claim the reward for it) or the payment
    failed."""
    return [r for r in recurrings if not r.active]


def record_names(snapshot: HouseholdSnapshot) -> list[str]:
    """Names of the loans and holdings that carry their own monthly
    figure. A detected pattern matching one of these is the *same money*
    seen from the other side of the books."""
    names = [
        (d.name or "").strip().casefold()
        for d in snapshot.debts
        if float(d.emi or 0) > 0 and float(d.outstanding or 0) > 0
    ]
    names += [
        (h.name or "").strip().casefold()
        for h in snapshot.investments
        if float(h.monthly_contribution or 0) > 0
    ]
    return [n for n in names if n]


def covered_by_record(item: Recurring, names: Sequence[str]) -> bool:
    """Whether a detected pattern is already accounted for by a Debt or
    Investment record.

    A user logs the EMI as "Home loan EMI" against a debt named "Home
    loan", and the SIP as "Axis Bluechip SIP" against a holding named
    "Axis Bluechip", so the match tolerates either string containing the
    other rather than demanding equality. `linked_to_portfolio` catches
    the rest: a row explicitly linked to a holding needs no name match at
    all.
    """
    if item.linked_to_portfolio:
        return True
    return any(name in item.key or item.key in name for name in names)
