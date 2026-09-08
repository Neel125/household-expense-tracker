"""Load sample September 2026 data into a fresh database.

Creates a demo household + owner login, seeds default categories and a
few accounts, and inserts the original spreadsheet's transactions so the
app opens with something to look at.

    python seed.py

Login afterwards with:  demo@ledger.app  /  demo1234
Safe to re-run: it skips if a household already exists.
"""
from sqlmodel import Session, select

from app.core.database import engine, init_db
from app.core.security import hash_password
from app.models import Account, Category, Household, Member, Transaction, User
from app.models.mixins import now_iso
from app.services.defaults import DEFAULT_CATEGORIES

DEMO_EMAIL = "demo@ledger.app"
DEMO_PASSWORD = "demo1234"
DEFAULT_MEMBER = "Neel"

# date, name, type, amount, payment_mode, provider_type, necessity, account, category, merchant
SEED_TRANSACTIONS = [
    ("2026-09-01", "Bike Fuel", "Expense", 930, "Credit Card", "OneCard", "Need", "", "Transport", "Indian Oil"),
    ("2026-09-02", "Bakery (Breads)", "Expense", 329, "UPI", "HDFC Bank", "Need", "", "Groceries", "Local Bakery"),
    ("2026-09-02", "Shaak + Maggi", "Expense", 215, "Cash", "Cash", "Need", "", "Groceries", "Kirana Store"),
    ("2026-09-02", "SSE Event (Baramu)", "Expense", 2100, "UPI", "HDFC Bank", "Want", "", "Entertainment", "SSE"),
    ("2026-09-03", "Curd + Cotton", "Expense", 45, "Cash", "Cash", "Need", "", "Groceries", "Kirana Store"),
    ("2026-09-04", "OneCard Repayment", "CC Repayment", 20000, "UPI", "HDFC Bank", "Debt", "OneCard", None, ""),
    ("2026-09-05", "Salary", "Income", 120000, "Net Banking", "HDFC Bank", "", "", None, "Employer"),
    ("2026-09-08", "SSE Maintenance", "Expense", 890, "UPI", "HDFC Bank", "Need", "", "Utilities", "SSE"),
    ("2026-09-09", "Paresh Bhai Post RD", "Investment", 11500, "UPI", "HDFC Bank", "Investment", "", None, ""),
    ("2026-09-10", "Home Loan EMI", "Loan", 26061, "Auto Debit", "HDFC Bank", "Debt", "Home Loan (HDFC)", "Housing", ""),
    ("2026-09-10", "ICICI Credit Card Repayment", "CC Repayment", 1359, "UPI", "HDFC Bank", "Debt", "ICICI Credit Card", None, ""),
    ("2026-09-10", "UTI Nifty 50 SIP", "Investment", 2000, "UPI", "HDFC Bank", "Investment", "", None, ""),
    ("2026-09-11", "Neel LIC", "Investment", 4679, "Credit Card", "OneCard", "Investment", "", "Insurance", "LIC"),
    ("2026-09-17", "Motilal Mid Cap Fund SIP", "Investment", 2000, "UPI", "HDFC Bank", "Investment", "", None, ""),
    ("2026-09-22", "Parag Parikh Flexi Cap SIP", "Investment", 5500, "UPI", "HDFC Bank", "Investment", "", None, ""),
    ("2026-09-22", "Bandhan Small Cap Fund", "Investment", 2000, "UPI", "HDFC Bank", "Investment", "", None, ""),
    ("2026-09-23", "Father Health Insurance", "Expense", 10350, "Credit Card", "OneCard", "Need", "", "Healthcare", "Star Health"),
    ("2026-09-25", "Nippon India Multi Cap SIP", "Investment", 3000, "UPI", "HDFC Bank", "Investment", "", None, ""),
    ("2026-09-27", "Car Loan EMI", "Loan", 11202, "Auto Debit", "AMCO Bank", "Debt", "Car Loan (AMCO Bank)", "Transport", ""),
]

SEED_ACCOUNTS = [
    ("HDFC Bank", "bank", "HDFC Bank", 85000),
    ("AMCO Bank", "bank", "AMCO Bank", 15000),
    ("Cash", "cash", "", 3000),
    ("OneCard", "credit_card", "", 0),
    ("ICICI Credit Card", "credit_card", "ICICI Bank", 0),
    ("Home Loan (HDFC)", "loan", "HDFC Bank", 0),
    ("Car Loan (AMCO Bank)", "loan", "AMCO Bank", 0),
]


def main() -> None:
    init_db()
    with Session(engine) as session:
        if session.exec(select(Household)).first():
            print("A household already exists — skipping seed.")
            return

        now = now_iso()
        household = Household(name="Demo household", monthly_budget=60000, created_at=now)
        session.add(household)
        session.commit()
        session.refresh(household)

        cat_by_name: dict[str, int] = {}
        for i, (name, color) in enumerate(DEFAULT_CATEGORIES):
            c = Category(household_id=household.id, name=name, color=color, is_custom=False, sort_order=i, created_at=now)
            session.add(c)
            session.commit()
            session.refresh(c)
            cat_by_name[name] = c.id

        for name, type_, inst, opening in SEED_ACCOUNTS:
            session.add(Account(household_id=household.id, name=name, type=type_, institution=inst, opening_balance=opening, created_at=now))

        member = Member(household_id=household.id, name=DEFAULT_MEMBER, relation="Self", created_at=now)
        session.add(member)
        session.commit()
        session.refresh(member)

        session.add(
            User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                display_name=DEFAULT_MEMBER,
                household_id=household.id,
                role="owner",
                member_id=member.id,
                created_at=now,
            )
        )

        for date, name, type_, amount, mode, provider, necessity, account, category, merchant in SEED_TRANSACTIONS:
            session.add(
                Transaction(
                    household_id=household.id,
                    date=date,
                    name=name,
                    type=type_,
                    amount=amount,
                    payment_mode=mode,
                    provider_type=provider,
                    necessity=necessity,
                    account=account,
                    member=DEFAULT_MEMBER,
                    category_id=cat_by_name.get(category) if category else None,
                    merchant=merchant,
                    created_at=now,
                )
            )
        session.commit()
        print(f"Seeded {len(SEED_TRANSACTIONS)} transactions. Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
