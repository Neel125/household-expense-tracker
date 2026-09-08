"""Concrete repositories. Most are just the generic base bound to a
model; the few with extra query needs add focused methods."""
from typing import Optional, Sequence

from sqlmodel import Session, select

from app.models import (
    Account,
    Category,
    CategoryBudget,
    Goal,
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
