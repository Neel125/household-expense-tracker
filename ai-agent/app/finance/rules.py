"""Merchant and keyword rules for categorising a transaction.

The point of this table is to keep the model out of the easy cases. A
household's ledger is mostly the same two dozen merchants repeating, and
paying an LLM to decide that Swiggy is food — every month, for every
row — is slow, costly and less consistent than a lookup. The model is
reserved for what the table genuinely cannot resolve.

Keys are the category names seeded in
`backend/app/services/defaults.py`. A household that renamed or archived
a category simply stops matching that rule (the id lookup returns None)
rather than the rule breaking — same failure mode the backend's reward
rules chose.

Tokens are matched case-insensitively against the transaction's merchant
and name, always on a **word boundary**. Substring matching is what makes
a table like this quietly wrong: 'ola' fires on 'Chocolate', 'bar' on
'chocolate bar', 'vi' on very nearly everything. A boundary match costs a
compiled regex per token and removes the entire class of bug, so every
token gets one — multi-word tokens ('amazon prime') and punctuated ones
('d-mart', 'booking.com', '1mg') included.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

# category name -> tokens that imply it
MERCHANT_RULES: dict[str, tuple[str, ...]] = {
    "Food & Dining": (
        "swiggy", "zomato", "eatsure", "dominos", "domino's", "pizza hut", "pizzahut",
        "mcdonald", "kfc", "burger king", "subway", "starbucks", "cafe coffee day",
        "ccd", "barista", "chaayos", "chai point", "third wave", "blue tokai",
        "restaurant", "dhaba", "biryani", "bakery", "eatery", "food court",
        "dineout", "eazydiner", "faasos", "behrouz", "ovenstory", "box8",
    ),
    "Groceries": (
        "bigbasket", "big basket", "blinkit", "grofers", "zepto", "instamart",
        "dmart", "d-mart", "d mart", "reliance fresh", "reliance smart", "more retail",
        "spencer", "nature's basket", "licious", "freshtohome", "fresh to home",
        "milk basket", "milkbasket", "country delight", "supermarket", "kirana",
        "provision", "vegetable", "grocery", "sabzi",
    ),
    "Transport": (
        "uber", "ola", "ola cabs", "rapido", "namma yatri", "blusmart", "blu smart", "meru",
        "irctc", "railway", "redbus", "abhibus", "ksrtc", "msrtc", "bmtc", "best bus",
        "metro", "dmrc", "fastag", "toll", "parking", "petrol", "diesel", "fuel",
        "indian oil", "iocl", "bharat petroleum", "bpcl", "hindustan petroleum",
        "hpcl", "shell", "nayara", "jio-bp", "bounce", "yulu", "vogo", "zoomcar",
        "revv", "auto rickshaw", "cab",
    ),
    "Housing": (
        "rent", "landlord", "maintenance charge", "society", "apartment",
        "housing society", "brokerage", "nobroker", "no broker", "flat rent",
        "property tax", "house tax", "plumber", "carpenter", "electrician",
        "painting", "renovation", "interior",
    ),
    "Utilities": (
        "electricity", "power bill", "bescom", "mseb", "msedcl", "tneb", "kseb",
        "adani electricity", "tata power", "torrent power", "bses", "water bill",
        "gas bill", "indane", "hp gas", "bharat gas", "lpg", "piped gas", "igl",
        "mahanagar gas", "broadband", "wifi", "airtel", "jio", "vodafone", "vodafone idea",
        "bsnl", "act fibernet", "hathway", "excitel", "tikona", "dish tv", "tata play",
        "recharge", "postpaid", "prepaid", "dth",
    ),
    "Healthcare": (
        "apollo", "fortis", "manipal", "max healthcare", "aiims", "medanta",
        "narayana health", "cloudnine", "pharmacy", "pharmeasy", "1mg", "tata 1mg",
        "netmeds", "medplus", "wellness forever", "hospital", "clinic", "diagnostic",
        "pathology", "lab test", "thyrocare", "dr lal", "srl diagnostics", "metropolis",
        "doctor", "dentist", "physio", "practo", "medicine", "chemist", "vaccination",
    ),
    "Shopping": (
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa", "tata cliq",
        "tatacliq", "snapdeal", "shopsy", "croma", "reliance digital", "vijay sales",
        "decathlon", "ikea", "pepperfry", "urban ladder", "westside", "lifestyle",
        "shoppers stop", "pantaloons", "zara", "h&m", "uniqlo", "max fashion",
        "trends", "bata", "puma", "adidas", "nike", "titan", "tanishq", "caratlane",
        "boat", "noise", "firstcry", "apple store",
    ),
    "Entertainment": (
        "bookmyshow", "book my show", "pvr", "inox", "cinepolis", "carnival cinema",
        "imax", "movie", "cinema", "multiplex", "gaming", "steam", "playstation",
        "xbox", "nintendo", "concert", "stand up", "standup", "amusement",
        "wonderla", "snow city", "bowling", "nightclub", "pub", "brewery",
        "sports bar", "lounge bar", "wine shop", "liquor",
    ),
    "Education": (
        "school fee", "college fee", "tuition", "coaching", "byju", "unacademy",
        "vedantu", "physics wallah", "toppr", "whitehat", "cuemath",
        "udemy", "coursera", "upgrad", "simplilearn", "great learning", "scaler",
        "exam fee", "university", "admission", "textbook", "stationery", "library",
    ),
    "Travel": (
        "makemytrip", "make my trip", "goibibo", "cleartrip", "yatra", "ixigo",
        "easemytrip", "airbnb", "oyo", "treebo", "fabhotels", "booking.com",
        "agoda", "trivago", "indigo", "air india", "vistara", "spicejet", "akasa",
        "airasia", "emirates", "qatar airways", "lufthansa", "flight", "hotel",
        "resort", "homestay", "visa fee", "passport", "forex", "travel insurance",
    ),
    "Subscriptions": (
        "netflix", "prime video", "amazon prime", "hotstar", "disney+", "jiocinema",
        "jiohotstar", "sonyliv", "zee5", "voot", "aha", "sun nxt", "mubi",
        "spotify", "gaana", "wynk", "youtube premium", "youtube music",
        "apple music", "icloud", "google one", "dropbox", "notion", "figma",
        "canva", "adobe", "microsoft 365", "office 365", "chatgpt", "openai",
        "claude", "github", "linkedin premium", "audible", "kindle unlimited",
        "cult.fit", "cultfit", "subscription", "membership", "renewal",
    ),
    "Personal Care": (
        "salon", "spa", "barber", "haircut", "parlour", "parlor", "urban company",
        "urbanclap", "looks salon", "naturals", "enrich", "lakme", "bodycraft",
        "gym", "fitness", "yoga", "zumba", "crossfit", "gold's gym", "anytime fitness",
        "grooming", "cosmetic",
    ),
    "Insurance": (
        "insurance", "premium", "lic", "life insurance", "hdfc life", "icici pru",
        "sbi life", "max life", "bajaj allianz", "tata aig", "star health",
        "niva bupa", "care health", "acko", "digit", "policybazaar", "policy bazaar",
        "term plan", "mediclaim", "health cover", "motor insurance",
    ),
    "Gifts": (
        "gift", "donation", "charity", "temple", "ngo", "gofundme", "milaap",
        "ketto", "wedding gift", "shagun", "birthday gift", "festival gift",
    ),
}

# Payment-mode and type hints that beat a merchant match. A row the user
# already typed as a loan payment is a debt row whatever the lender is
# called.
TYPE_RULES: dict[str, str] = {
    "Loan": "Housing",
    "Loan Partial": "Housing",
}

_BOUNDARY_CACHE: dict[str, re.Pattern[str]] = {}


def _pattern(token: str) -> re.Pattern[str]:
    """A cached word-boundary matcher for one token.

    `\b` is only meaningful next to a word character, so a token that
    starts or ends with punctuation gets the boundary dropped on that
    side — otherwise the pattern could never match.
    """
    cached = _BOUNDARY_CACHE.get(token)
    if cached is None:
        lead = r"\b" if token[:1].isalnum() else ""
        trail = r"\b" if token[-1:].isalnum() else ""
        cached = re.compile(f"{lead}{re.escape(token)}{trail}")
        _BOUNDARY_CACHE[token] = cached
    return cached


def _matches(token: str, haystack: str) -> bool:
    return bool(token) and _pattern(token).search(haystack) is not None


def match_category_name(text: Iterable[str]) -> Optional[tuple[str, str]]:
    """Return (category name, the token that fired) for the first rule
    that matches, or None.

    Longer tokens are tried first across the whole table, so 'amazon
    prime' is a subscription before 'amazon' makes it shopping. That
    ordering is the only reason the two can coexist.
    """
    haystack = " ".join(part.casefold() for part in text if part).strip()
    if not haystack:
        return None
    for token, category in _ORDERED_TOKENS:
        if _matches(token, haystack):
            return category, token
    return None


# Built once at import: every (token, category) pair, longest token first.
_ORDERED_TOKENS: list[tuple[str, str]] = sorted(
    ((token, category) for category, tokens in MERCHANT_RULES.items() for token in tokens),
    key=lambda pair: len(pair[0]),
    reverse=True,
)
