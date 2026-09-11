"""Daily playables: quiz, puzzle and the coin wheel.

These sit next to the habit challenges but they are *games* — the user
plays them in the app, the server scores them, and a successful round
pays a random coin amount. Definitions live here so the engine (and the
UI copy) never hard-code a question or a payout range.

One attempt per household per game per local day. A failed quiz or
puzzle still consumes the attempt, so guessing until it pays is closed.
"""
from dataclasses import dataclass

KIND_QUIZ = "GAME_QUIZ"
KIND_PUZZLE = "GAME_PUZZLE"
KIND_SPIN = "GAME_SPIN"

QUIZ_PASS_SCORE = 4
QUIZ_QUESTION_COUNT = 5
QUIZ_PAYOUT = (25, 80)
PUZZLE_PAYOUT = (20, 70)


@dataclass(frozen=True)
class GameDef:
    key: str
    title: str
    description: str
    icon: str
    payout_min: int
    payout_max: int
    hint: str


GAMES: list[GameDef] = [
    GameDef(
        KIND_QUIZ,
        "Daily money quiz",
        "Five questions on budgets, EMIs and investing. Get four right to unlock a random coin drop.",
        "🧠",
        *QUIZ_PAYOUT,
        "New set every day · 4 of 5 to win",
    ),
    GameDef(
        KIND_PUZZLE,
        "Daily money puzzle",
        "A sorter, a riddle or a match-up — one puzzle a day, random coins if you crack it.",
        "🧩",
        *PUZZLE_PAYOUT,
        "One try a day · type rotates",
    ),
    GameDef(
        KIND_SPIN,
        "Spin the wheel",
        "Give the wheel a whirl. Wherever it lands is today's bonus — 10 to 100 coins.",
        "🎡",
        10,
        100,
        "One spin a day · prize is the slice",
    ),
]
GAMES_BY_KEY: dict[str, GameDef] = {g.key: g for g in GAMES}


# ---------------------------------------------------------------- quiz bank
@dataclass(frozen=True)
class QuizQuestion:
    id: str
    prompt: str
    options: tuple[str, ...]
    correct: int  # index into options


QUIZ_BANK: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        "q_503020",
        "In the 50/30/20 rule, the 20% is meant for…",
        ("Eating out", "Saving and investing", "Shopping", "Rent"),
        1,
    ),
    QuizQuestion(
        "q_emi",
        "EMI stands for…",
        (
            "Estimated Monthly Income",
            "Equated Monthly Instalment",
            "Early Money Injection",
            "Extra Mortgage Interest",
        ),
        1,
    ),
    QuizQuestion(
        "q_emergency",
        "A solid emergency fund is typically…",
        (
            "One week of shopping money",
            "3–6 months of essential expenses",
            "Your credit-card limit",
            "Whatever is left on the 31st",
        ),
        1,
    ),
    QuizQuestion(
        "q_want_need",
        "Which of these is a Want, not a Need?",
        ("Rent", "Groceries", "Concert tickets", "Medicines"),
        2,
    ),
    QuizQuestion(
        "q_sip",
        "A SIP is best described as…",
        (
            "A one-time stock purchase",
            "Investing a fixed amount at regular intervals",
            "A type of home loan",
            "Paying a credit-card bill in parts",
        ),
        1,
    ),
    QuizQuestion(
        "q_fd_vs_savings",
        "Compared with a savings account, a fixed deposit usually…",
        (
            "Pays a higher interest rate but locks the money in",
            "Lets you withdraw anytime with no penalty",
            "Tracks the stock market",
            "Has no interest at all",
        ),
        0,
    ),
    QuizQuestion(
        "q_credit_interest",
        "Credit-card interest is charged on…",
        (
            "The full credit limit, every month",
            "The unpaid balance after the due date",
            "Every swipe, even if you pay in full",
            "Only international spends",
        ),
        1,
    ),
    QuizQuestion(
        "q_inflation",
        "If inflation is 6% and your savings earn 4%, your money's real value…",
        ("Grows by 10%", "Stays the same", "Falls by about 2%", "Doubles"),
        2,
    ),
    QuizQuestion(
        "q_budget",
        "The first job of a monthly budget is to…",
        (
            "Stop you from ever spending on fun",
            "Decide where money goes before it arrives",
            "Max out every credit card",
            "Hide subscriptions",
        ),
        1,
    ),
    QuizQuestion(
        "q_compound",
        "Compound interest means you earn interest on…",
        (
            "Only the original principal",
            "Principal plus interest already earned",
            "Only the last month's deposit",
            "Your neighbour's account",
        ),
        1,
    ),
    QuizQuestion(
        "q_prepay",
        "A prepayment on a home loan typically…",
        (
            "Raises the EMI forever",
            "Cuts outstanding principal, so less interest accrues",
            "Is illegal after the first year",
            "Converts the loan into an FD",
        ),
        1,
    ),
    QuizQuestion(
        "q_rd",
        "A recurring deposit (RD) is…",
        (
            "A one-time lump-sum deposit",
            "A monthly deposit for a fixed tenure",
            "A stock-market product",
            "A type of credit card",
        ),
        1,
    ),
    QuizQuestion(
        "q_net_worth",
        "Household net worth is…",
        (
            "Income minus rent",
            "Assets minus debts",
            "The credit-card limit",
            "Only the money in cash",
        ),
        1,
    ),
    QuizQuestion(
        "q_diversify",
        "Diversifying investments means…",
        (
            "Putting everything in one hot stock",
            "Spreading money across different kinds of assets",
            "Keeping it all under the mattress",
            "Taking a new loan every year",
        ),
        1,
    ),
    QuizQuestion(
        "q_cc_repay",
        "Paying a credit-card bill in full by the due date…",
        (
            "Still attracts a month of interest",
            "Avoids interest on that cycle",
            "Lowers your credit limit",
            "Is worse than paying the minimum",
        ),
        1,
    ),
    QuizQuestion(
        "q_goal",
        "The most useful financial goal has…",
        (
            "A target amount and a date",
            "Only a vibe",
            "No number, so it can't fail",
            "Someone else's deadline",
        ),
        0,
    ),
    QuizQuestion(
        "q_min_pay",
        "Paying only the credit-card minimum due…",
        (
            "Clears the card that month",
            "Stretches the debt and piles on interest",
            "Earns you a bonus",
            "Is required by law",
        ),
        1,
    ),
    QuizQuestion(
        "q_ppf",
        "PPF is primarily a…",
        (
            "Short-term spending account",
            "Long-term retirement / tax-saving instrument",
            "Type of car loan",
            "Cryptocurrency wallet",
        ),
        1,
    ),
)


# ------------------------------------------------------------- puzzles
@dataclass(frozen=True)
class SorterItem:
    id: str
    label: str
    bucket: str  # need | want | invest


@dataclass(frozen=True)
class MatchPair:
    id: str
    term: str
    definition: str


@dataclass(frozen=True)
class Puzzle:
    id: str
    kind: str  # sorter | riddle | match
    title: str
    prompt: str
    items: tuple = ()
    options: tuple[str, ...] = ()
    correct: int = 0  # riddle only


PUZZLE_BANK: tuple[Puzzle, ...] = (
    Puzzle(
        "p_sorter_home",
        "sorter",
        "Need, Want or Invest?",
        "Tap each card until the bucket is right. Needs keep the household running, Wants are optional, Invest is money you put to work.",
        items=(
            SorterItem("rent", "Monthly rent / EMI", "need"),
            SorterItem("groceries", "Weekly groceries", "need"),
            SorterItem("netflix", "Streaming subscription", "want"),
            SorterItem("sip", "Mutual-fund SIP", "invest"),
            SorterItem("concert", "Concert tickets", "want"),
            SorterItem("ppf", "PPF contribution", "invest"),
        ),
    ),
    Puzzle(
        "p_sorter_weekend",
        "sorter",
        "Need, Want or Invest?",
        "Sort these. Be honest — a treat is still a Want even if it felt earned.",
        items=(
            SorterItem("electricity", "Electricity bill", "need"),
            SorterItem("school", "School fees", "need"),
            SorterItem("gadgets", "New phone on EMI", "want"),
            SorterItem("fd", "Bank fixed deposit", "invest"),
            SorterItem("swiggy", "Weekend food delivery", "want"),
            SorterItem("gold", "Sovereign gold bond", "invest"),
        ),
    ),
    Puzzle(
        "p_riddle_503020",
        "riddle",
        "The 50/30/20 split",
        "A household takes home ₹80,000 this month and follows 50/30/20. How much should go to saving and investing?",
        options=("₹8,000", "₹16,000", "₹24,000", "₹40,000"),
        correct=1,  # 20% of 80k = 16k
    ),
    Puzzle(
        "p_riddle_emi",
        "riddle",
        "What's left after EMI",
        "Take-home is ₹70,000. Home EMI is ₹22,000, SIPs are ₹8,000, groceries ₹12,000. How much is left for everything else?",
        options=("₹20,000", "₹28,000", "₹36,000", "₹48,000"),
        correct=1,  # 70 - 22 - 8 - 12 = 28
    ),
    Puzzle(
        "p_riddle_emergency",
        "riddle",
        "Emergency-fund size",
        "Essential monthly spend is ₹40,000. A 6-month emergency fund should be about…",
        options=("₹40,000", "₹80,000", "₹1,20,000", "₹2,40,000"),
        correct=3,  # 40k * 6 = 2.4L
    ),
    Puzzle(
        "p_match_terms",
        "match",
        "Match the money words",
        "Pair each term with its meaning.",
        items=(
            MatchPair("emi", "EMI", "Fixed monthly loan repayment"),
            MatchPair("sip", "SIP", "Regular investment into a fund"),
            MatchPair("fd", "FD", "Lump sum locked with a bank for a tenure"),
            MatchPair("rd", "RD", "Monthly deposits into a bank scheme"),
        ),
    ),
    Puzzle(
        "p_match_habits",
        "match",
        "Match the habit to the payoff",
        "Drag each behaviour to what it usually earns you — in real life, not just coins.",
        items=(
            MatchPair("budget", "Staying in budget", "Money left at month-end"),
            MatchPair("review", "Reviewing last month", "Catching leaks early"),
            MatchPair("goal", "Funding a goal", "A dated target getting closer"),
            MatchPair("cc", "Paying the card in full", "Avoiding interest"),
        ),
    ),
)


# ---------------------------------------------------------------- wheel
@dataclass(frozen=True)
class WheelSlice:
    coins: int
    label: str
    color: str


WHEEL_SLICES: tuple[WheelSlice, ...] = (
    WheelSlice(10, "10", "#7c9a8e"),
    WheelSlice(25, "25", "#3d8b7a"),
    WheelSlice(15, "15", "#c4a35a"),
    WheelSlice(50, "50", "#2f6f9e"),
    WheelSlice(20, "20", "#8b6b4a"),
    WheelSlice(75, "75", "#c45c26"),
    WheelSlice(30, "30", "#5b7c5b"),
    WheelSlice(100, "100", "#b33b3b"),
)
