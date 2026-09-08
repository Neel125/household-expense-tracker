"""Concrete repositories. Most are just the generic base bound to a
model; the few with extra query needs add focused methods."""
from typing import Optional, Sequence

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    Account,
    Category,
    CategoryBudget,
    ChallengeEnrollment,
    CoinTransaction,
    Goal,
    HealthSnapshot,
    Household,
    IncomeSource,
    Invite,
    Member,
    Transaction,
    User,
)
from app.repositories.base import HouseholdRepository


class TransactionRepository(HouseholdRepository[Transaction]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Transaction)

    def list(self, household_id: int) -> Sequence[Transaction]:
        stmt = (
            select(Transaction)
            .where(Transaction.household_id == household_id)
            .order_by(Transaction.date.desc())
        )
        return self.session.exec(stmt).all()

    def count_created_since(self, household_id: int, since_iso: str) -> int:
        """Rows *entered* since a timestamp (not rows dated since then) —
        the signal the rewards engine's burst detector needs."""
        stmt = select(func.count(Transaction.id)).where(
            Transaction.household_id == household_id,
            Transaction.created_at >= since_iso,
        )
        return int(self.session.exec(stmt).one() or 0)

    def for_member(self, household_id: int, name: str) -> Sequence[Transaction]:
        stmt = select(Transaction).where(
            Transaction.household_id == household_id, Transaction.member == name
        )
        return self.session.exec(stmt).all()


class MemberRepository(HouseholdRepository[Member]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Member)

    def find_by_name(self, household_id: int, name: str) -> Optional[Member]:
        key = (name or "").casefold()
        for m in self.list(household_id):
            if m.name.casefold() == key:
                return m
        return None


class AccountRepository(HouseholdRepository[Account]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Account)


class CategoryRepository(HouseholdRepository[Category]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Category)

    def list(self, household_id: int) -> Sequence[Category]:
        stmt = (
            select(Category)
            .where(Category.household_id == household_id)
            .order_by(Category.sort_order, Category.id)
        )
        return self.session.exec(stmt).all()


class CategoryBudgetRepository(HouseholdRepository[CategoryBudget]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, CategoryBudget)


class IncomeSourceRepository(HouseholdRepository[IncomeSource]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, IncomeSource)


class GoalRepository(HouseholdRepository[Goal]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Goal)


class CoinTransactionRepository(HouseholdRepository[CoinTransaction]):
    """The coin ledger. Append-only: no update or delete is exposed, and
    the balance is always derived, never stored."""

    def __init__(self, session: Session) -> None:
        super().__init__(session, CoinTransaction)

    def balance(self, household_id: int) -> int:
        stmt = select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
            CoinTransaction.household_id == household_id
        )
        return int(self.session.exec(stmt).one() or 0)

    def find_by_event_key(self, household_id: int, event_key: str) -> Optional[CoinTransaction]:
        stmt = select(CoinTransaction).where(
            CoinTransaction.household_id == household_id,
            CoinTransaction.event_key == event_key,
        )
        return self.session.exec(stmt).first()

    def history(self, household_id: int, limit: int = 50) -> Sequence[CoinTransaction]:
        stmt = (
            select(CoinTransaction)
            .where(CoinTransaction.household_id == household_id)
            .order_by(CoinTransaction.id.desc())
            .limit(limit)
        )
        return self.session.exec(stmt).all()

    def earned_for_kind_since(self, household_id: int, kind: str, since_iso: str) -> int:
        """Coins already paid by one rule since a timestamp — how the daily
        cap is enforced without a counter table to keep in sync."""
        stmt = select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
            CoinTransaction.household_id == household_id,
            CoinTransaction.kind == kind,
            CoinTransaction.created_at >= since_iso,
        )
        return int(self.session.exec(stmt).one() or 0)

    def totals_by_kind(self, household_id: int) -> dict[str, int]:
        stmt = (
            select(CoinTransaction.kind, func.coalesce(func.sum(CoinTransaction.amount), 0))
            .where(CoinTransaction.household_id == household_id)
            .group_by(CoinTransaction.kind)
        )
        return {kind: int(total or 0) for kind, total in self.session.exec(stmt).all()}


class ChallengeEnrollmentRepository(HouseholdRepository[ChallengeEnrollment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ChallengeEnrollment)

    def find(self, household_id: int, challenge_key: str, period: str) -> Optional[ChallengeEnrollment]:
        stmt = select(ChallengeEnrollment).where(
            ChallengeEnrollment.household_id == household_id,
            ChallengeEnrollment.challenge_key == challenge_key,
            ChallengeEnrollment.period == period,
        )
        return self.session.exec(stmt).first()


class HealthSnapshotRepository(HouseholdRepository[HealthSnapshot]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, HealthSnapshot)

    def find(self, household_id: int, month: str) -> Optional[HealthSnapshot]:
        stmt = select(HealthSnapshot).where(
            HealthSnapshot.household_id == household_id, HealthSnapshot.month == month
        )
        return self.session.exec(stmt).first()


class HouseholdRepo:
    """Households aren't scoped by household_id (they *are* the scope), so
    this one doesn't extend HouseholdRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, household_id: int) -> Optional[Household]:
        return self.session.get(Household, household_id)

    def add(self, obj: Household) -> Household:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def save(self, obj: Household) -> Household:
        return self.add(obj)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: int) -> Optional[User]:
        return self.session.get(User, user_id)

    def find_by_email(self, email: str) -> Optional[User]:
        key = (email or "").strip().casefold()
        stmt = select(User)
        for u in self.session.exec(stmt).all():
            if u.email.casefold() == key:
                return u
        return None

    def add(self, obj: User) -> User:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def save(self, obj: User) -> User:
        return self.add(obj)


class InviteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self, household_id: int) -> Sequence[Invite]:
        stmt = (
            select(Invite)
            .where(Invite.household_id == household_id)
            .order_by(Invite.id.desc())
        )
        return self.session.exec(stmt).all()

    def find_by_token(self, token: str) -> Optional[Invite]:
        stmt = select(Invite).where(Invite.token == token)
        return self.session.exec(stmt).first()

    def add(self, obj: Invite) -> Invite:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def save(self, obj: Invite) -> Invite:
        return self.add(obj)
