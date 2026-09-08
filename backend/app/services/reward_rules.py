"""The reward catalogue: what behaviour earns what, plus levels and
challenges.

One deliberate product rule runs through all of it: **coins reward
financial discipline, never spending**. Logging an expense is worth a
single coin (and is capped per day) because tracking is the habit worth
building; the large payouts sit on staying inside a budget, saving more
than last month, finishing a goal and dropping a subscription. Nothing
here scales with the amount spent, so there is no way to earn more by
spending more.

Everything is data so the engine stays dumb: services.rewards_service
looks rules up by key and never hard-codes a coin value.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rule:
    key: str
    coins: int
    label: str
    # Most coins/day this rule may ever pay. None = uncapped (used for
    # rules that are already once-per-period by construction).
    daily_cap: int | None = None


RULES: dict[str, Rule] = {
    r.key: r
    for r in [
        Rule("EXPENSE_TRACKED", 1, "Expense logged", daily_cap=10),
        Rule("TRACKING_STREAK_7", 20, "7-day tracking streak"),
        Rule("BUDGET_KEPT", 100, "Stayed within the monthly budget"),
        Rule("SAVINGS_IMPROVED", 150, "Saved more than last month"),
        Rule("GOAL_COMPLETED", 500, "Financial goal completed"),
        Rule("SUBSCRIPTION_DROPPED", 100, "Unused subscription cancelled"),
        Rule("MONTHLY_REVIEW", 25, "Monthly spending reviewed"),
        Rule("EMERGENCY_FUND_ON_TARGET", 200, "Emergency fund at target"),
        # Portfolio building blocks. Tracking a new investment earns a
        # nudge coin (capped per day so bulk-imports can't farm it);
        # reaching maturity pays a proper milestone. Reversal is the
        # mirror that keeps a create/delete loop honest.
        Rule("INVESTMENT_ADDED", 25, "Investment tracked", daily_cap=100),
        Rule("INVESTMENT_MATURED", 100, "Investment matured"),
        # Loan payoffs. The tier is the *kind* of loan closed — a home
        # loan is years of discipline, a consumer EMI is a few months, so
        # the coin values reflect the effort rather than the ticket size.
        Rule("LOAN_COMPLETED_HOME", 1000, "Home loan paid off"),
        Rule("LOAN_COMPLETED_CAR", 500, "Car loan paid off"),
        Rule("LOAN_COMPLETED_OTHER", 100, "Loan paid off"),
        # Variable payouts: the amount comes from the challenge definition
        # / the size of the score improvement, so `coins` is unused.
        Rule("CHALLENGE_COMPLETED", 0, "Challenge completed"),
        Rule("HEALTH_SCORE_IMPROVED", 0, "Financial health improved"),
        # Debits. Reversal keeps the ledger honest when a rewarded action
        # is undone; redemption is reserved so spending coins later needs
        # no schema change (see README — the MVP has nothing to buy).
        Rule("EXPENSE_REVERSED", 0, "Logged expense deleted"),
        Rule("INVESTMENT_REVERSED", 0, "Tracked investment deleted"),
        Rule("REWARD_REDEMPTION", 0, "Reward redeemed"),
    ]
}

# Rows written for auditability that intentionally pay nothing.
FLAGGED = "AWARD_FLAGGED"


def coins_for(key: str) -> int:
    rule = RULES.get(key)
    return rule.coins if rule else 0


def label_for(key: str) -> str:
    rule = RULES.get(key)
    return rule.label if rule else key.replace("_", " ").title()


# --------------------------------------------------------------- abuse limits
# The create-expense/delete-expense farm loop from the design review: the
# reversal already nets it to zero, and these keep even the attempt cheap.
MIN_REWARDABLE_AMOUNT = 1.0  # a ₹0 entry is not tracking
BURST_WINDOW_SECONDS = 300
# Measured against expenses *created*, not coins awarded: the daily cap
# already limits awards to 10, so an award-based threshold could never
# fire. One entry every five seconds, sustained for five minutes, is a
# script — a person bulk-entering receipts stays well under this.
BURST_MAX_EVENTS = 60


# --------------------------------------------------------------------- levels
@dataclass(frozen=True)
class Level:
    number: int
    name: str
    icon: str
    min_coins: int
    perks: list[str] = field(default_factory=list)


LEVELS: list[Level] = [
    Level(1, "Beginner", "🌱", 0, ["Coin history", "Daily tracking streak"]),
    Level(2, "Saver", "🌿", 500, ["Monthly challenges", "Savings-rate trend"]),
    Level(3, "Smart Saver", "🌳", 2000, ["Merchant analysis", "Custom reports"]),
    Level(4, "Financial Pro", "💎", 5000, ["Full analytics suite", "Priority insights"]),
]


def level_for(balance: int) -> Level:
    current = LEVELS[0]
    for level in LEVELS:
        if balance >= level.min_coins:
            current = level
    return current


def next_level(balance: int) -> Level | None:
    for level in LEVELS:
        if balance < level.min_coins:
            return level
    return None


# ----------------------------------------------------------------- challenges
@dataclass(frozen=True)
class Challenge:
    key: str
    title: str
    description: str
    coins: int
    period: str  # "month" | "week"
    icon: str
    # What "done" looks like, for the progress caption.
    unit: str = ""


CHALLENGES: list[Challenge] = [
    Challenge(
        "no_spend_weekend",
        "No-Spend Weekend",
        "Make no discretionary (Want) purchases on Saturday and Sunday.",
        100,
        "week",
        "🛑",
        "weekend days clear",
    ),
    Challenge(
        "no_shopping_7_days",
        "No Unnecessary Shopping",
        "Seven days with nothing logged to Shopping or Entertainment.",
        120,
        "week",
        "🛍️",
        "days clear",
    ),
    Challenge(
        "track_every_expense",
        "Track Every Expense",
        "Log at least one transaction on every day of the month.",
        200,
        "month",
        "📊",
        "days tracked",
    ),
    Challenge(
        "save_5000",
        "Save ₹5,000 This Month",
        "Finish the month with income minus spending above ₹5,000.",
        150,
        "month",
        "💰",
        "saved",
    ),
    Challenge(
        "cut_eating_out",
        "Cut Eating Out by 20%",
        "Spend at least 20% less on Food & Dining than last month.",
        150,
        "month",
        "☕",
        "of the cut",
    ),
]

CHALLENGES_BY_KEY: dict[str, Challenge] = {c.key: c for c in CHALLENGES}

# Category names the discretionary-spend challenges key off. Matched
# case-insensitively against the household's own categories, so renaming
# or archiving one simply takes it out of scope.
DISCRETIONARY_CATEGORIES = {"shopping", "entertainment"}
EATING_OUT_CATEGORIES = {"food & dining"}
SUBSCRIPTION_CATEGORIES = {"subscriptions"}


# ------------------------------------------------------------------- loans
# Which coin rule to fire when a debt of a given kind is paid off. The
# map only lists the tiers explicitly rewarded; anything not here falls
# through to the "other" tier (consumer/personal/education/…). Keeping
# this in reward_rules — not the debt service — means the reward rate
# for a kind can be re-tiered without touching business logic.
LOAN_COMPLETION_RULES: dict[str, str] = {
    "home_loan": "LOAN_COMPLETED_HOME",
    "car_loan": "LOAN_COMPLETED_CAR",
}
LOAN_COMPLETION_DEFAULT = "LOAN_COMPLETED_OTHER"


def loan_rule_for(debt_kind: str) -> str:
    """The reward rule key for closing a debt of this kind."""
    return LOAN_COMPLETION_RULES.get((debt_kind or "").strip().lower(), LOAN_COMPLETION_DEFAULT)
