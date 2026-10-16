"""The tools the agent is allowed to use.

Every tool is a **closure over one already-loaded household snapshot**,
built fresh per request by `build_tools`. That is the whole tenancy
design: a tool takes no household id, so there is no id for the model to
get wrong and no way for a prompt injected through a transaction name to
ask about someone else's books. Graph construction is microseconds
against an LLM call measured in seconds, so per-request construction
costs nothing worth optimising away.

Every figure a tool returns comes from `app/finance/`, which is plain
arithmetic over the ledger. The model is never asked to add anything up;
it is asked to decide what the sums mean. The system prompt says the
same thing, but the reason it holds is that the numbers never pass
through the model on their way to being computed.

Tool results are compact JSON. Lists are capped — an agent that pulls
900 transactions into context has already lost — and every truncation is
announced in the payload so the model knows it is looking at a sample
rather than a total.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from langchain_core.tools import BaseTool, tool

from app.data.models import TYPE_EXPENSE
from app.data.snapshot import HouseholdSnapshot
from app.finance import (
    anomaly,
    budget as budget_mod,
    categorize,
    forecast as forecast_mod,
    goals as goals_mod,
    obligations as obligations_mod,
    portfolio as portfolio_mod,
    recurring as recurring_mod,
    report as report_mod,
)
from app.finance.month import (
    in_month,
    month_label,
    pct_change,
    prev_month_key,
    this_month_key,
    totals_for,
)

# Caps. Generous enough to answer a real question, small enough that a
# careless call cannot blow the context window.
MAX_ROWS = 60
MAX_SUGGESTIONS = 40

# 'YYYY-MM', with a month in 01..12. Years are left unbounded: the books
# may hold a loan maturing in 2047 and there is no harm in asking.
_MONTH_KEY = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")


def _json(payload: Any) -> str:
    return json.dumps(payload, default=str, separators=(",", ":"), ensure_ascii=False)


def _capped(rows: list, limit: int) -> tuple[list, Optional[str]]:
    if len(rows) <= limit:
        return rows, None
    return rows[:limit], (
        f"Showing {limit} of {len(rows)}. Narrow the filters to see the rest — "
        f"do not treat this as a complete list."
    )


def build_tools(snapshot: HouseholdSnapshot) -> list[BaseTool]:
    """Bind every tool to one household's books."""
    today = snapshot.as_of
    current_month = this_month_key(today)
    last_month = prev_month_key(current_month)

    def _month(value: Optional[str]) -> str:
        """Accept 'YYYY-MM', a full date, or nothing.

        Anything else falls back to the current month rather than being
        passed on. A small local model will occasionally hand a month
        parameter something that is not a month at all — a tool name, a
        category, the word "last" — and the month arithmetic downstream
        slices the string without checking, so an unvalidated value
        surfaces as `int('get_')` and kills the whole run. Silently
        defaulting is the right failure here: the month is stated back in
        every tool's own response, so a wrong guess is visible to the
        model and correctable on the next call, whereas a crash is not.
        """
        cleaned = (value or "").strip()[:7]
        if not _MONTH_KEY.fullmatch(cleaned):
            return current_month
        return cleaned

    # ------------------------------------------------------------ context
    @tool
    def get_household_overview() -> str:
        """Start here. Returns who this household is, its monthly budget and
        income, how much history exists, how much of it is categorised, and
        the current and previous month keys. Call this before any other tool
        so later answers use real month keys instead of guessed ones."""
        months = sorted({(t.date or "")[:7] for t in snapshot.transactions if t.date})
        return _json(
            {
                "household": snapshot.household.name,
                "asOf": today.isoformat(),
                "currentMonth": current_month,
                "currentMonthLabel": month_label(current_month),
                "previousMonth": last_month,
                "monthlyBudget": snapshot.monthly_budget,
                "budgetIsSet": snapshot.monthly_budget > 0,
                "recurringMonthlyIncome": snapshot.recurring_monthly_income,
                "members": [
                    {"name": m.name, "relation": m.relation, "monthlyBudget": m.monthly_budget}
                    for m in snapshot.members
                ],
                "categories": [c.name for c in snapshot.active_categories],
                "counts": {
                    "transactions": len(snapshot.transactions),
                    "investments": len(snapshot.investments),
                    "debts": len(snapshot.debts),
                    "goals": len(snapshot.goals),
                    "accounts": len(snapshot.accounts),
                },
                "monthsWithData": months,
                "categorisation": categorize.coverage(snapshot),
            }
        )

    @tool
    def list_transactions(
        month: Optional[str] = None,
        category_name: Optional[str] = None,
        merchant: Optional[str] = None,
        member: Optional[str] = None,
        min_amount: Optional[float] = None,
        limit: int = 30,
    ) -> str:
        """List individual transactions, newest first, for looking at the rows
        behind a total. `month` is 'YYYY-MM' and defaults to the current
        month. All other filters are optional and combine with AND. Use this
        to answer 'what was that spend?', not to add anything up — the
        totalling tools are exact and this one is capped."""
        rows = in_month(snapshot.transactions, _month(month))
        if category_name:
            key = category_name.casefold()
            rows = [t for t in rows if snapshot.category_name(t.category_id).casefold() == key]
        if merchant:
            key = merchant.casefold()
            rows = [t for t in rows if key in (t.merchant or t.name or "").casefold()]
        if member:
            key = member.casefold()
            rows = [t for t in rows if (t.member or "").casefold() == key]
        if min_amount is not None:
            rows = [t for t in rows if float(t.amount or 0) >= min_amount]

        rows.sort(key=lambda t: ((t.date or ""), t.id or 0), reverse=True)
        shown, note = _capped(rows, min(max(1, limit), MAX_ROWS))
        return _json(
            {
                "month": _month(month),
                "matched": len(rows),
                "sumOfMatched": round(sum(float(t.amount or 0) for t in rows), 2),
                "note": note,
                "transactions": [
                    {
                        "id": t.id,
                        "date": t.date,
                        "name": t.name,
                        "merchant": t.merchant,
                        "amount": round(float(t.amount or 0), 2),
                        "type": t.type,
                        "category": snapshot.category_name(t.category_id),
                        "necessity": t.necessity,
                        "member": t.member,
                        "paymentMode": t.payment_mode,
                    }
                    for t in shown
                ],
            }
        )

    @tool
    def get_spending_by_category(month: Optional[str] = None) -> str:
        """Exact totals per category for one month, each with the previous
        month's figure and the percentage change. This is the authoritative
        breakdown — quote these numbers rather than summing transactions."""
        mk = _month(month)
        previous = prev_month_key(mk)
        now: dict[Optional[int], float] = {}
        before: dict[Optional[int], float] = {}
        for txn in in_month(snapshot.transactions, mk):
            if txn.type == TYPE_EXPENSE:
                now[txn.category_id] = now.get(txn.category_id, 0.0) + float(txn.amount or 0)
        for txn in in_month(snapshot.transactions, previous):
            if txn.type == TYPE_EXPENSE:
                before[txn.category_id] = before.get(txn.category_id, 0.0) + float(txn.amount or 0)

        totals = totals_for(snapshot.transactions, mk)
        rows = sorted(
            (
                {
                    "category": snapshot.category_name(cid),
                    "amount": round(amount, 2),
                    "previousAmount": round(before.get(cid, 0.0), 2),
                    "changePct": pct_change(amount, before.get(cid, 0.0)),
                }
                for cid, amount in now.items()
            ),
            key=lambda row: -row["amount"],
        )
        return _json(
            {"month": mk, "label": month_label(mk), "totals": totals.as_dict(), "categories": rows}
        )

    @tool
    def compare_months(month_a: str, month_b: str) -> str:
        """Compare two months side by side ('YYYY-MM' each): totals, and the
        categories that moved most between them. Use this for 'why was last
        month worse?' questions."""
        a, b = _month(month_a), _month(month_b)
        totals_a, totals_b = (
            totals_for(snapshot.transactions, a),
            totals_for(snapshot.transactions, b),
        )

        def by_category(mk: str) -> dict[str, float]:
            out: dict[str, float] = {}
            for txn in in_month(snapshot.transactions, mk):
                if txn.type == TYPE_EXPENSE:
                    name = snapshot.category_name(txn.category_id)
                    out[name] = out.get(name, 0.0) + float(txn.amount or 0)
            return out

        left, right = by_category(a), by_category(b)
        moves = sorted(
            (
                {
                    "category": name,
                    f"{a}": round(left.get(name, 0.0), 2),
                    f"{b}": round(right.get(name, 0.0), 2),
                    "change": round(right.get(name, 0.0) - left.get(name, 0.0), 2),
                }
                for name in set(left) | set(right)
            ),
            key=lambda row: -abs(row["change"]),
        )
        return _json(
            {
                a: totals_a.as_dict(),
                b: totals_b.as_dict(),
                "spendChange": round(totals_b.spend - totals_a.spend, 2),
                "spendChangePct": pct_change(totals_b.spend, totals_a.spend),
                "biggestMoves": moves[:12],
            }
        )

    # ------------------------------------------------- 1. categorisation
    @tool
    def get_uncategorised_transactions(limit: int = 25) -> str:
        """Capability 1. Returns expenses with no category, split into two
        groups: `resolved`, which rules or this household's own past choices
        already settled, and `needsYourJudgement`, which they could not.

        Only assign categories for the rows in `needsYourJudgement`, choosing
        from `availableCategories` exactly as spelled. Leave the resolved
        ones alone — repeating them adds nothing and risks contradicting a
        precedent the household already set."""
        resolved, unresolved = categorize.suggest(snapshot, limit=MAX_SUGGESTIONS)
        shown, note = _capped(unresolved, min(max(1, limit), MAX_SUGGESTIONS))
        return _json(
            {
                "availableCategories": [c.name for c in snapshot.active_categories],
                "coverage": categorize.coverage(snapshot),
                "resolved": [s.as_dict() for s in resolved],
                "note": note,
                "needsYourJudgement": [
                    {
                        "transactionId": t.id,
                        "date": t.date,
                        "name": t.name,
                        "merchant": t.merchant,
                        "amount": round(float(t.amount or 0), 2),
                        "necessity": t.necessity,
                        "paymentMode": t.payment_mode,
                        "member": t.member,
                    }
                    for t in shown
                ],
            }
        )

    # ----------------------------------------------------- 2. anomalies
    @tool
    def detect_spending_anomalies(month: Optional[str] = None) -> str:
        """Capability 2. Statistically unusual spending for a month, judged
        against this household's own six-month history using a median-based
        score. Covers category spikes, outsized single charges, first-time
        large payees, payees appearing far more often than usual, probable
        duplicate charges, and standing payments that did not arrive.

        Each finding carries the amount and the baseline it was compared
        against. Report those figures; do not recompute them."""
        mk = _month(month)
        found = anomaly.detect(snapshot, mk)
        return _json(
            {
                "month": mk,
                "label": month_label(mk),
                "count": len(found),
                "bySeverity": {
                    level: sum(1 for a in found if a.severity == level)
                    for level in ("high", "medium", "low")
                },
                "anomalies": [a.as_dict() for a in found[:25]],
            }
        )

    # -------------------------------------------------------- 3. budget
    @tool
    def get_budget_status(month: Optional[str] = None) -> str:
        """Capability 3. Budget versus actual for a month, per category and
        overall. Includes `expectedPct` (the share of the budget that should
        have been used by today, pro-rated by days elapsed), a straight-line
        `projected` month-end figure, and `safeDailyRateForRest` — what the
        household can spend per day for the rest of the month and still come
        in on budget. For a month still running, judge by the projection, not
        by the amount spent so far."""
        return _json(budget_mod.status(snapshot, _month(month)).as_dict())

    # ------------------------------------------------------ 4. forecast
    @tool
    def forecast_next_month(from_month: Optional[str] = None) -> str:
        """Capability 4. Forecast the month after `from_month` (default: the
        month after this one).

        The forecast is split into `committed` — rent, EMIs, SIPs,
        subscriptions, all of them already decided — and `variable`, which is
        estimated per category from trailing medians with a damped trend.
        Always report the range (`low` to `high`) and the `confidence`, and
        say what `basis` says the forecast rests on. A point estimate quoted
        alone overstates what can be known."""
        return _json(forecast_mod.forecast(snapshot, _month(from_month)).as_dict())

    # --------------------------------------------- 5 & 6. portfolio/debt
    @tool
    def analyse_portfolio() -> str:
        """Capabilities 5 and 6. The whole investment and debt picture:
        every holding with its invested amount, current value, gain and
        annualised return; allocation by asset kind; single-holding
        concentration; SIPs and RDs with no recent contribution; deposits
        maturing soon; every open loan with its outstanding balance, months
        remaining and interest still to run; and net worth.

        `annualisedPct` is null for a holding under a year old — annualising
        a few months magnifies noise, so it is withheld rather than
        overstated. Say so rather than substituting the raw gain."""
        return _json(portfolio_mod.analyse(snapshot).as_dict())

    @tool
    def get_credit_card_balances() -> str:
        """Capability 6. What is outstanding on each credit card, computed
        with this app's accrual rules: a card purchase counts on the day it
        is made, and a repayment settles it rather than counting as a second
        expense."""
        return _json({"cards": obligations_mod.credit_card_balances(snapshot)})

    @tool
    def get_recurring_payments() -> str:
        """Capability 6. Standing commitments detected from the ledger —
        rent, subscriptions, utilities — with the typical amount, the day of
        the month they fall on, and whether they still look active.

        `lapsed` entries stopped arriving: either the household cancelled the
        subscription, or a payment failed. Both are worth raising, and they
        need different advice, so do not assume which it is."""
        items = recurring_mod.detect(snapshot)
        names = recurring_mod.record_names(snapshot)
        # EMIs and SIPs are reported by analyse_portfolio from their own
        # records; listing them here too would double the committed total.
        household_only = [r for r in items if not recurring_mod.covered_by_record(r, names)]
        return _json(
            {
                "monthlyCommitted": round(
                    sum(r.typical_amount for r in household_only if r.active), 2
                ),
                "active": [r.as_dict() for r in household_only if r.active],
                "lapsed": [r.as_dict() for r in household_only if not r.active],
            }
        )

    # ------------------------------------------------------- 7. billing
    @tool
    def get_upcoming_obligations(horizon_days: int = 45) -> str:
        """Capability 7. Every dated commitment inside the horizon, soonest
        first: recurring bills, loan EMIs, SIP and RD instalments, deposits
        maturing, expiring vehicle papers and unpaid challans.

        An `amount` of null means the cost genuinely is not knowable from the
        records — a policy renewal price, for instance. Say it is unknown
        rather than estimating one."""
        return _json(obligations_mod.summary(snapshot, max(1, min(horizon_days, 180))))

    # -------------------------------------------------------- 8. report
    @tool
    def get_monthly_report_data(month: Optional[str] = None) -> str:
        """Capability 8. Every figure a monthly report could quote, for one
        month: income, outflow, savings rate, category breakdown with
        month-on-month changes, top merchants, per-member spend, budget
        adherence, portfolio and net worth, goals, and a six-month trend.
        Defaults to last completed month, which is the one worth reporting
        on. This is a large payload — read it once and write from it."""
        mk = (month or "").strip()[:7] or prev_month_key(current_month)
        return _json(report_mod.build(snapshot, mk))

    # --------------------------------------------------------- 9. goals
    @tool
    def get_goal_progress() -> str:
        """Capability 9. Every savings goal with its progress, the monthly
        contribution needed to hit its target date, and whether the
        household's real surplus can cover all of them at once.

        `surplus` is measured over completed months only — a month still
        running always looks like a surplus because its spending has not all
        happened yet. `emergencyFund` and `expensiveDebt` carry the two rules
        that outrank ordinary goals; `priorityRules` states them."""
        return _json(goals_mod.analyse(snapshot))

    return [
        get_household_overview,
        list_transactions,
        get_spending_by_category,
        compare_months,
        get_uncategorised_transactions,
        detect_spending_anomalies,
        get_budget_status,
        forecast_next_month,
        analyse_portfolio,
        get_credit_card_balances,
        get_recurring_payments,
        get_upcoming_obligations,
        get_monthly_report_data,
        get_goal_progress,
    ]
