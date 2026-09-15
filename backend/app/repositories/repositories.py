"""Concrete repositories. Most are just the generic base bound to a
model; the few with extra query needs add focused methods."""
from typing import Optional, Sequence

from sqlalchemy import and_, func, or_
from sqlmodel import Session, select

from app.models import (
    Account,
    Category,
    CategoryBudget,
    ChallengeEnrollment,
    CoinTransaction,
    Debt,
    Goal,
    HealthSnapshot,
    Household,
    IncomeSource,
    Investment,
    Invite,
    Member,
    Referral,
    Transaction,
    User,
)
from app.models.transaction import LOAN_PAYMENT_TYPES
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

    def for_investment(self, household_id: int, investment_id: int) -> Sequence[Transaction]:
        """Contributions to one holding. The type filter matters: a row
        re-typed away from Investment stops counting even if the link is
        still on it."""
        stmt = select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.investment_id == investment_id,
            Transaction.type == "Investment",
        )
        return self.session.exec(stmt).all()

    def for_debt(self, household_id: int, debt_id: int) -> Sequence[Transaction]:
        """EMIs and partial payments against one debt."""
        stmt = select(Transaction).where(
            Transaction.household_id == household_id,
            Transaction.debt_id == debt_id,
            Transaction.type.in_(LOAN_PAYMENT_TYPES),
        )
        return self.session.exec(stmt).all()

    def portfolio_linked(self, household_id: int) -> Sequence[Transaction]:
        """Every row linked to a holding, in one query — so a portfolio
        listing costs one round trip rather than one per holding."""
        stmt = select(Transaction).where(
            Transaction.household_id == household_id,
            or_(
                and_(Transaction.investment_id.is_not(None), Transaction.type == "Investment"),
                and_(
                    Transaction.debt_id.is_not(None),
                    Transaction.type.in_(LOAN_PAYMENT_TYPES),
                ),
            ),
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


class InvestmentRepository(HouseholdRepository[Investment]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Investment)


class DebtRepository(HouseholdRepository[Debt]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Debt)


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

    def count_for_kind_since(self, household_id: int, kind: str, since_iso: str) -> int:
        stmt = select(func.count(CoinTransaction.id)).where(
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


class ReferralRepository:
    """A referral row links two households, so the generic
    household-scoped base doesn't fit: every query has to say which side
    of the relationship it means."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, obj: Referral) -> Referral:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def save(self, obj: Referral) -> Referral:
        return self.add(obj)

    def made_by(self, household_id: int) -> Sequence[Referral]:
        """Referrals this household sent out, newest first."""
        stmt = (
            select(Referral)
            .where(Referral.referrer_household_id == household_id)
            .order_by(Referral.id.desc())
        )
        return self.session.exec(stmt).all()

    def for_referred(self, household_id: int) -> Optional[Referral]:
        """The referral that brought this household in, if any."""
        stmt = select(Referral).where(Referral.referred_household_id == household_id)
        return self.session.exec(stmt).first()


class HouseholdRepo:
    """Households aren't scoped by household_id (they *are* the scope), so
    this one doesn't extend HouseholdRepository."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, household_id: int) -> Optional[Household]:
        return self.session.get(Household, household_id)

    def find_by_referral_code(self, code: str) -> Optional[Household]:
        key = (code or "").strip().upper()
        if not key:
            return None
        stmt = select(Household).where(Household.referral_code == key)
        return self.session.exec(stmt).first()

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
