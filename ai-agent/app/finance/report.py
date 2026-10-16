"""Capability 8 — assemble the facts a monthly financial report is
written from.

This module produces no prose. It gathers every figure the report could
need — income, outflow, savings rate, category and merchant breakdowns,
who spent what, budget adherence, net worth, and the same month a year
and a month ago — and hands them over as one payload. The model's job is
to decide which of them matter this month and say so in a paragraph.

That division is the reason the service can be trusted with money: a
figure in the report either came from here or it is wrong, and the
prompt says so.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from app.data.models import TYPE_EXPENSE, TYPE_INCOME
from app.data.snapshot import HouseholdSnapshot
from app.finance import budget as budget_mod
from app.finance import goals as goals_mod
from app.finance import portfolio as portfolio_mod
from app.finance.month import (
    in_month,
    is_complete,
    month_income,
    month_label,
    pct_change,
    prev_month_key,
    recent_month_keys,
    shift_month,
    this_month_key,
    totals_for,
)

TOP_N = 8
TREND_MONTHS = 6


def _breakdown(snapshot: HouseholdSnapshot, mk: str, previous_mk: str) -> list[dict]:
    """Spend per category this month against the same month before, so
    every line answers 'and is that a lot?' on its own."""
    now: dict[Optional[int], float] = defaultdict(float)
    count: dict[Optional[int], int] = defaultdict(int)
    for txn in in_month(snapshot.transactions, mk):
        if txn.type == TYPE_EXPENSE:
            now[txn.category_id] += float(txn.amount or 0)
            count[txn.category_id] += 1

    before: dict[Optional[int], float] = defaultdict(float)
    for txn in in_month(snapshot.transactions, previous_mk):
        if txn.type == TYPE_EXPENSE:
            before[txn.category_id] += float(txn.amount or 0)

    total = sum(now.values())
    rows = [
        {
            "categoryId": category_id,
            "categoryName": snapshot.category_name(category_id),
            "amount": round(amount, 2),
            "sharePct": round(amount / total * 100, 1) if total > 0 else 0.0,
            "transactionCount": count[category_id],
            "previousAmount": round(before.get(category_id, 0.0), 2),
            "changePct": pct_change(amount, before.get(category_id, 0.0)),
        }
        for category_id, amount in now.items()
    ]
    return sorted(rows, key=lambda row: -row["amount"])


def _merchants(snapshot: HouseholdSnapshot, mk: str) -> list[dict]:
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for txn in in_month(snapshot.transactions, mk):
        if txn.type != TYPE_EXPENSE:
            continue
        payee = (txn.merchant or txn.name or "").strip()
        if not payee:
            continue
        totals[payee] += float(txn.amount or 0)
        counts[payee] += 1
    rows = [
        {"merchant": name, "amount": round(amount, 2), "transactionCount": counts[name]}
        for name, amount in totals.items()
    ]
    return sorted(rows, key=lambda row: -row["amount"])[:TOP_N]


def _members(snapshot: HouseholdSnapshot, mk: str) -> list[dict]:
    """Per person, using the same accrual rules as the household totals.
    Untagged rows get their own line rather than vanishing."""
    totals: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for txn in in_month(snapshot.transactions, mk):
        if txn.type != TYPE_EXPENSE:
            continue
        who = (txn.member or "").strip() or "Untagged"
        totals[who] += float(txn.amount or 0)
        counts[who] += 1

    caps = {m.name: float(m.monthly_budget or 0) for m in snapshot.members}
    grand = sum(totals.values())
    rows = []
    for name, amount in totals.items():
        cap = caps.get(name, 0.0)
        rows.append(
            {
                "member": name,
                "amount": round(amount, 2),
                "transactionCount": counts[name],
                "sharePct": round(amount / grand * 100, 1) if grand > 0 else 0.0,
                "personalBudget": round(cap, 2),
                "overBudgetBy": round(max(0.0, amount - cap), 2) if cap > 0 else 0.0,
            }
        )
    return sorted(rows, key=lambda row: -row["amount"])


def build(snapshot: HouseholdSnapshot, mk: Optional[str] = None) -> dict:
    """Every figure a monthly report could quote, for one month."""
    mk = mk or prev_month_key(this_month_key(snapshot.as_of))
    previous_mk = prev_month_key(mk)
    year_ago_mk = shift_month(mk, -12)

    totals = totals_for(snapshot.transactions, mk)
    before = totals_for(snapshot.transactions, previous_mk)
    year_ago = totals_for(snapshot.transactions, year_ago_mk)

    recurring_income = snapshot.recurring_monthly_income
    income = month_income(totals, recurring_income)
    # Savings is what income did not have to cover, investments included:
    # money moved into an SIP is saved, not spent.
    saved = income - totals.spend

    budget_status = budget_mod.status(snapshot, mk)
    portfolio = portfolio_mod.analyse(snapshot)
    goal_view = goals_mod.analyse(snapshot)

    trend = [
        totals_for(snapshot.transactions, key).as_dict()
        for key in recent_month_keys(mk, TREND_MONTHS)
    ]

    income_rows = [
        {
            "name": txn.name,
            "amount": round(float(txn.amount or 0), 2),
            "date": txn.date,
            "member": txn.member,
        }
        for txn in in_month(snapshot.transactions, mk)
        if txn.type == TYPE_INCOME
    ]

    return {
        "month": mk,
        "label": month_label(mk),
        "isComplete": is_complete(mk, snapshot.as_of),
        "asOf": snapshot.as_of.isoformat(),
        "household": snapshot.household.name,
        "income": {
            "total": round(income, 2),
            "recurring": round(recurring_income, 2),
            "oneOff": round(totals.txn_income, 2),
            "sources": income_rows,
        },
        "outflow": {
            "spend": round(totals.spend, 2),
            "expenses": round(totals.expenses, 2),
            "loanPayments": round(totals.loan_payments, 2),
            "investments": round(totals.investments, 2),
            "needs": round(totals.needs, 2),
            "wants": round(totals.wants, 2),
            "transactionCount": totals.transaction_count,
        },
        "savings": {
            "amount": round(saved, 2),
            "ratePct": round(saved / income * 100, 1) if income > 0 else 0.0,
            "investedThisMonth": round(totals.investments, 2),
        },
        "comparison": {
            "previousMonth": previous_mk,
            "spendChangePct": pct_change(totals.spend, before.spend),
            "spendChangeAmount": round(totals.spend - before.spend, 2),
            "previousSpend": round(before.spend, 2),
            "yearAgoMonth": year_ago_mk,
            "yearAgoSpend": round(year_ago.spend, 2),
            "yearAgoChangePct": pct_change(totals.spend, year_ago.spend),
        },
        "categories": _breakdown(snapshot, mk, previous_mk),
        "topMerchants": _merchants(snapshot, mk),
        "members": _members(snapshot, mk),
        "budget": budget_status.as_dict(),
        "netWorth": {
            "investments": round(portfolio.current_value, 2),
            "debt": round(portfolio.total_debt, 2),
            "creditCardOutstanding": 0.0,  # filled by the caller when needed
            "net": round(portfolio.net_worth, 2),
        },
        "portfolio": {
            "totalInvested": round(portfolio.total_invested, 2),
            "currentValue": round(portfolio.current_value, 2),
            "gainPct": portfolio.gain_pct,
            "monthlyCommitment": round(portfolio.monthly_commitment, 2),
            "allocation": portfolio.allocation,
        },
        "goals": goal_view["goals"],
        "emergencyFund": goal_view["emergencyFund"],
        "surplus": goal_view["surplus"],
        "trend": trend,
    }
