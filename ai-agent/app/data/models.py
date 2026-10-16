"""Read-only mirrors of the backend's tables.

These are deliberately *thin* copies of `backend/app/models/` — only the
columns the analysis needs, with no relationships, no validation and no
defaults that could disagree with the writer. The backend owns the
schema; this module owns a read view of it.

Duplication is the price of keeping the agent in its own container. It is
bounded and cheap to keep honest: these are plain column lists, and a
column the backend adds is simply invisible here until someone adds it.
A column the backend *removes* fails loudly on the next query, which is
the behaviour worth having.

`SQLModel.metadata.create_all()` is never called against these — see
app/core/database.py.
"""
from typing import Optional

from sqlmodel import Field, SQLModel

# Transaction types, as the backend spells them on the wire.
TYPE_EXPENSE = "Expense"
TYPE_INCOME = "Income"
TYPE_INVESTMENT = "Investment"
TYPE_INVESTMENT_WITHDRAWAL = "Investment Withdrawal"
TYPE_LOAN = "Loan"
TYPE_LOAN_PARTIAL = "Loan Partial"
TYPE_CC_REPAYMENT = "CC Repayment"

LOAN_PAYMENT_TYPES = (TYPE_LOAN, TYPE_LOAN_PARTIAL)
# Neither is day-to-day consumption: a repayment is cash settling a
# purchase already counted on the day it was made, and income is not
# spend. An investment withdrawal is money coming back from a holding,
# not new income and not spend. Kept identical to
# backend/app/services/month_math.py.
NOT_SPEND = {TYPE_CC_REPAYMENT, TYPE_INCOME, TYPE_INVESTMENT_WITHDRAWAL}
CONSUMPTION_TYPES = {TYPE_EXPENSE, TYPE_LOAN, TYPE_LOAN_PARTIAL}

# Investment kinds that are a standing monthly commitment rather than a
# one-off purchase — the ones worth watching for a missed instalment.
RECURRING_INVESTMENT_KINDS = {"sip", "rd"}
# Kinds that mature on a date and need a "what next" decision.
MATURING_INVESTMENT_KINDS = {"fd", "rd", "bond"}


class Household(SQLModel, table=True):
    __tablename__ = "household"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = ""
    monthly_budget: float = 0
    referral_code: str = ""
    created_at: str = ""


class Member(SQLModel, table=True):
    __tablename__ = "member"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    relation: str = ""
    monthly_budget: float = 0


class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    color: str = ""
    is_custom: bool = False
    archived: bool = False
    sort_order: int = 0


class CategoryBudget(SQLModel, table=True):
    __tablename__ = "categorybudget"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    category_id: int = Field(index=True)
    percentage: float = 0


class IncomeSource(SQLModel, table=True):
    __tablename__ = "incomesource"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    kind: str = "salary"
    monthly_amount: float = 0
    member: str = ""
    active: bool = True


class Account(SQLModel, table=True):
    __tablename__ = "account"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    type: str = "bank"
    institution: str = ""
    opening_balance: float = 0
    linked_account_id: Optional[int] = None
    archived: bool = False


class Goal(SQLModel, table=True):
    __tablename__ = "goal"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    kind: str = "custom"
    target_amount: float = 0
    saved_amount: float = 0
    target_date: str = ""


class Investment(SQLModel, table=True):
    __tablename__ = "investment"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    kind: str = "other"
    institution: str = ""
    amount_invested: float = 0
    current_value: float = 0
    annual_return_pct: float = 0
    monthly_contribution: float = 0
    start_date: str = ""
    maturity_date: str = ""
    notes: str = ""
    closed: bool = False
    closed_at: str = ""
    closed_to_account: str = ""
    successor_id: Optional[int] = None
    created_at: str = ""


class Debt(SQLModel, table=True):
    __tablename__ = "debt"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    kind: str = "other"
    lender: str = ""
    principal: float = 0
    outstanding: float = 0
    annual_rate_pct: float = 0
    emi: float = 0
    tenure_months: int = 0
    months_paid: int = 0
    start_date: str = ""


class Transaction(SQLModel, table=True):
    __tablename__ = "transaction"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    date: str = ""  # YYYY-MM-DD
    name: str = ""
    type: str = ""
    amount: float = 0
    payment_mode: str = ""
    provider_type: str = ""
    necessity: str = ""
    account: str = ""
    member: str = ""
    category_id: Optional[int] = None
    merchant: str = ""
    investment_id: Optional[int] = None
    debt_id: Optional[int] = None
    created_at: str = ""


class Vehicle(SQLModel, table=True):
    __tablename__ = "vehicle"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    name: str = ""
    kind: str = "car"
    registration: str = ""


class VehicleRecord(SQLModel, table=True):
    __tablename__ = "vehicle_record"

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True)
    vehicle_id: int = Field(index=True)
    kind: str = ""
    title: str = ""
    date: str = ""
    expiry_date: str = ""
    amount: float = 0
    status: str = ""
