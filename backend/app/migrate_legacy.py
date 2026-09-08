"""One-time migration from the old single-tenant schema.

The previous app had no households/users and kept cards/loans in a
settings row. If we find pre-existing Transaction/Member rows without a
household, we fold them into a default household and create an owner
login so nothing is lost. Safe to run on every startup — it does nothing
once a household exists.
"""
import json

from sqlalchemy import inspect, text
from sqlmodel import Session, select

from app.core.database import engine
from app.core.security import hash_password
from app.models import Account, Category, Household, Member, Transaction, User
from app.models.mixins import now_iso
from app.services.defaults import DEFAULT_CATEGORIES

LEGACY_EMAIL = "owner@example.com"
LEGACY_PASSWORD = "changeme123"


def migrate_legacy_data() -> None:
    with Session(engine) as session:
        if session.exec(select(Household)).first():
            return  # already migrated / fresh multi-tenant DB

        legacy_txns = session.exec(select(Transaction)).all()
        legacy_members = session.exec(select(Member)).all()
        if not legacy_txns and not legacy_members:
            return  # nothing to migrate; a fresh DB registers normally

        now = now_iso()
        household = Household(name="My household", created_at=now)
        session.add(household)
        session.commit()
        session.refresh(household)

        for i, (name, color) in enumerate(DEFAULT_CATEGORIES):
            session.add(
                Category(
                    household_id=household.id,
                    name=name,
                    color=color,
                    is_custom=False,
                    sort_order=i,
                    created_at=now,
                )
            )

        for m in legacy_members:
            m.household_id = household.id
            session.add(m)
        for t in legacy_txns:
            t.household_id = household.id
            session.add(t)

        _migrate_settings_accounts(session, household.id, now)

        owner_name = legacy_members[0].name if legacy_members else "Owner"
        owner_member_id = legacy_members[0].id if legacy_members else None
        session.add(
            User(
                email=LEGACY_EMAIL,
                password_hash=hash_password(LEGACY_PASSWORD),
                display_name=owner_name,
                household_id=household.id,
                role="owner",
                member_id=owner_member_id,
                created_at=now,
            )
        )
        session.commit()
        print(
            f"Migrated {len(legacy_txns)} transactions into a household. "
            f"Login: {LEGACY_EMAIL} / {LEGACY_PASSWORD} (change it)."
        )


def _migrate_settings_accounts(session: Session, household_id: int, now: str) -> None:
    """Turn the old settingsrow cards/loans/opening balances into Account rows."""
    inspector = inspect(engine)
    if "settingsrow" not in inspector.get_table_names():
        return
    row = session.exec(text("SELECT cards_json, loans_json, opening_balances_json FROM settingsrow WHERE id = 1")).first()
    if not row:
        return
    cards = json.loads(row[0] or "[]")
    loans = json.loads(row[1] or "[]")
    opening = json.loads(row[2] or "{}")
    for name in cards:
        session.add(
            Account(
                household_id=household_id,
                name=name,
                type="credit_card",
                opening_balance=float(opening.get(name, 0) or 0),
                created_at=now,
            )
        )
    for name in loans:
        session.add(Account(household_id=household_id, name=name, type="loan", created_at=now))
    session.commit()
