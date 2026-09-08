"""Seed data used when a household is first created."""

# (name, css-var color). Predefined categories every household starts
# with; users can rename, archive, or add their own.
DEFAULT_CATEGORIES: list[tuple[str, str]] = [
    ("Food & Dining", "var(--series-1)"),
    ("Groceries", "var(--series-2)"),
    ("Transport", "var(--series-3)"),
    ("Housing", "var(--series-4)"),
    ("Utilities", "var(--series-5)"),
    ("Healthcare", "var(--series-6)"),
    ("Shopping", "var(--series-1)"),
    ("Entertainment", "var(--series-2)"),
    ("Education", "var(--series-3)"),
    ("Travel", "var(--series-4)"),
    ("Subscriptions", "var(--series-5)"),
    ("Personal Care", "var(--series-6)"),
    ("Insurance", "var(--series-1)"),
    ("Gifts", "var(--series-2)"),
    ("Other", "var(--series-3)"),
]
