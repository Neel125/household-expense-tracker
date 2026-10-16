"""Household investments (FD/RD/SIP/stocks/etc.).

Beyond simple CRUD, this service is where the "investment" domain
publishes the two facts the rewards engine listens for: a new investment
was tracked, and an existing one hit its maturity date. The service
itself never awards coins — it only fires the event, keeping the reward
catalogue as the single source of truth for how much anything is worth.

Withdraw and reinvest are the two maturity actions: close the holding
and credit a bank, or roll the proceeds into a successor. Reinvest
logs a transaction only for the add-on, not for the matured principal.
"""
from datetime import date
from typing import Optional

from sqlmodel import Session

from app.models import Investment, Transaction
from app.models.account import DEPOSIT_ACCOUNT_TYPES
from app.models.investment import INVESTMENT_KINDS
from app.models.mixins import now_iso
from app.models.transaction import TYPE_INVESTMENT, TYPE_INVESTMENT_WITHDRAWAL
from app.repositories.repositories import AccountRepository, InvestmentRepository
from app.schemas.investment import InvestmentIn, InvestmentReinvestIn, InvestmentWithdrawIn
from app.services import events
from app.services.errors import NotFoundError, ValidationError
from app.services.portfolio_service import PortfolioService


class InvestmentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.investments = InvestmentRepository(session)
        self.accounts = AccountRepository(session)
        self.portfolio = PortfolioService(session)

    def list(self, household_id: int):
        return self.investments.list(household_id)

    def create(
        self, household_id: int, data: InvestmentIn, actor_id: Optional[int] = None
    ) -> Investment:
        payload = self._validate(data)
        obj = self.investments.add(
            Investment(
                household_id=household_id,
                created_at=now_iso(),
                **payload,
            )
        )
        self._announce_added(obj, actor_id)
        self._announce_matured(obj, actor_id)
        return obj

    def update(
        self,
        household_id: int,
        obj_id: int,
        data: InvestmentIn,
        actor_id: Optional[int] = None,
    ) -> Investment:
        obj = self.investments.get(household_id, obj_id)
        if not obj:
            raise NotFoundError("Investment not found")
        for k, v in self._validate(data).items():
            setattr(obj, k, v)
        obj.updated_at = now_iso()
        obj = self.investments.save(obj)
        # An investment can only cross its maturity line once; the
        # ledger's idempotency key ensures a re-save of a matured row
        # never pays a second time.
        self._announce_matured(obj, actor_id)
        return obj

    def delete(self, household_id: int, obj_id: int, actor_id: Optional[int] = None) -> None:
        obj = self.investments.get(household_id, obj_id)
        if not obj:
            raise NotFoundError("Investment not found")
        # Capture what we need for the event *before* the row is gone.
        payload = {"investment_id": obj.id, "name": obj.name}
        self.investments.delete(obj)
        events.publish(
            self.session,
            events.DomainEvent(
                name=events.INVESTMENT_DELETED,
                household_id=household_id,
                user_id=actor_id,
                payload=payload,
            ),
        )

    def withdraw(
        self,
        household_id: int,
        obj_id: int,
        data: InvestmentWithdrawIn,
        actor_id: Optional[int] = None,
    ) -> Investment:
        """Close a holding and credit its proceeds to a deposit account.

        The credit is an `Investment Withdrawal` transaction: it raises
        the bank balance without counting as household income.
        """
        obj = self._open_holding(household_id, obj_id)
        account = self._deposit_account(household_id, data.account_name)
        _, view = self.portfolio.investment_view(household_id, obj.id)
        amount = self._proceeds(data.amount, view.effective_value)
        if amount <= 0:
            raise ValidationError("Nothing to withdraw — the holding has no value")
        day = self._action_date(data.date)

        self.session.add(
            self._withdrawal_txn(
                household_id,
                obj,
                amount=amount,
                day=day,
                account_name=account.name,
                member=data.member,
                payment_mode=data.payment_mode,
            )
        )
        self._close(obj, day=day, account_name=account.name)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        self._announce_matured(obj, actor_id)
        return obj

    def reinvest(
        self,
        household_id: int,
        obj_id: int,
        data: InvestmentReinvestIn,
        actor_id: Optional[int] = None,
    ) -> tuple[Investment, Investment]:
        """Close a holding and open a successor funded by the matured
        proceeds plus an optional add-on.

        The matured principal stays invested — it is the new holding's
        opening figure, not a bank movement. The only transaction logged
        is the add-on, extra money leaving the chosen account.
        """
        obj = self._open_holding(household_id, obj_id)
        _, view = self.portfolio.investment_view(household_id, obj.id)
        proceeds = self._proceeds(data.amount, view.effective_value)
        add_on = max(0.0, float(data.add_on_amount or 0))
        if proceeds + add_on <= 0:
            raise ValidationError("Reinvest needs the matured value or an add-on amount")
        account = None
        if add_on > 0:
            account = self._deposit_account(household_id, data.account_name)
        day = self._action_date(data.date)
        rate = (
            float(data.annual_return_pct)
            if data.annual_return_pct is not None
            else float(obj.annual_return_pct or 0)
        )
        new_name = (data.new_name or "").strip() or f"{obj.name} (renewed)"
        monthly = float(obj.monthly_contribution or 0) if obj.kind in {"sip", "rd"} else 0.0

        successor = Investment(
            household_id=household_id,
            name=new_name,
            kind=obj.kind,
            institution=obj.institution,
            # Rolled principal is opening capital, not a fresh debit.
            amount_invested=proceeds,
            current_value=0,
            annual_return_pct=rate,
            monthly_contribution=monthly,
            start_date=day,
            maturity_date=(data.new_maturity_date or "").strip(),
            notes=(data.notes or "").strip(),
            created_at=now_iso(),
        )
        self.session.add(successor)
        self.session.flush()

        if add_on > 0 and account is not None:
            self.session.add(
                self._contribution_txn(
                    household_id,
                    successor,
                    amount=add_on,
                    day=day,
                    account_name=account.name,
                    member=data.member,
                    payment_mode=data.payment_mode,
                    name=f"{new_name} — add-on",
                )
            )

        self._close(
            obj,
            day=day,
            account_name=account.name if account else "",
            successor_id=successor.id,
        )
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        self.session.refresh(successor)
        self._announce_matured(obj, actor_id)
        self._announce_added(successor, actor_id)
        return obj, successor

    # ---------------------------------------------------------- publishing
    def _announce_added(self, obj: Investment, actor_id: Optional[int]) -> None:
        events.publish(
            self.session,
            events.DomainEvent(
                name=events.INVESTMENT_ADDED,
                household_id=obj.household_id,
                user_id=actor_id,
                payload={
                    "investment_id": obj.id,
                    "name": obj.name,
                    "kind": obj.kind,
                },
            ),
        )

    def _announce_matured(self, obj: Investment, actor_id: Optional[int]) -> None:
        """Publish INVESTMENT_MATURED if the row's maturity_date is set
        and has already passed. Handler side is idempotent, so callers
        can invoke this on every save without worrying about repeats."""
        if not self._is_matured(obj):
            return
        events.publish(
            self.session,
            events.DomainEvent(
                name=events.INVESTMENT_MATURED,
                household_id=obj.household_id,
                user_id=actor_id,
                payload={
                    "investment_id": obj.id,
                    "name": obj.name,
                    "kind": obj.kind,
                    "maturity_date": obj.maturity_date,
                },
            ),
        )

    @staticmethod
    def _is_matured(obj: Investment) -> bool:
        raw = (obj.maturity_date or "").strip()
        if not raw:
            return False
        try:
            return date.fromisoformat(raw[:10]) <= date.today()
        except ValueError:
            # A malformed date can't be "matured" — better silent than
            # crashing a save because someone typed the month wrong.
            return False

    def _open_holding(self, household_id: int, obj_id: int) -> Investment:
        obj = self.investments.get(household_id, obj_id)
        if not obj:
            raise NotFoundError("Investment not found")
        if obj.closed:
            raise ValidationError("That investment is already closed")
        return obj

    def _deposit_account(self, household_id: int, name: str):
        key = (name or "").strip()
        if not key:
            raise ValidationError("Pick the bank account for this transfer")
        for acc in self.accounts.list(household_id):
            if acc.archived:
                continue
            if acc.name == key and acc.type in DEPOSIT_ACCOUNT_TYPES:
                return acc
        raise ValidationError("Pick a bank, debit or cash account")

    @staticmethod
    def _action_date(raw: str) -> str:
        value = (raw or "").strip() or date.today().isoformat()
        try:
            return date.fromisoformat(value[:10]).isoformat()
        except ValueError as exc:
            raise ValidationError("Use a date like YYYY-MM-DD") from exc

    @staticmethod
    def _proceeds(override: Optional[float], fallback: float) -> float:
        amount = float(fallback if override is None else override)
        if amount < 0:
            raise ValidationError("Amount can't be negative")
        return round(amount, 2)

    @staticmethod
    def _close(
        obj: Investment,
        *,
        day: str,
        account_name: str,
        successor_id: Optional[int] = None,
    ) -> None:
        obj.closed = True
        obj.closed_at = day
        obj.closed_to_account = account_name
        obj.successor_id = successor_id
        obj.monthly_contribution = 0
        obj.updated_at = now_iso()

    @staticmethod
    def _withdrawal_txn(
        household_id: int,
        obj: Investment,
        *,
        amount: float,
        day: str,
        account_name: str,
        member: str,
        payment_mode: str,
    ) -> Transaction:
        return Transaction(
            household_id=household_id,
            date=day,
            name=f"{obj.name} — withdrawn",
            type=TYPE_INVESTMENT_WITHDRAWAL,
            amount=amount,
            payment_mode=(payment_mode or "Net Banking").strip() or "Net Banking",
            provider_type=account_name,
            necessity="",
            account="",
            member=(member or "").strip(),
            merchant="",
            investment_id=obj.id,
            created_at=now_iso(),
        )

    @staticmethod
    def _contribution_txn(
        household_id: int,
        obj: Investment,
        *,
        amount: float,
        day: str,
        account_name: str,
        member: str,
        payment_mode: str,
        name: str,
    ) -> Transaction:
        return Transaction(
            household_id=household_id,
            date=day,
            name=name,
            type=TYPE_INVESTMENT,
            amount=amount,
            payment_mode=(payment_mode or "Net Banking").strip() or "Net Banking",
            provider_type=account_name,
            necessity="Investment",
            account="",
            member=(member or "").strip(),
            merchant="",
            investment_id=obj.id,
            created_at=now_iso(),
        )

    # ---------------------------------------------------------- validation
    @staticmethod
    def _validate(data: InvestmentIn) -> dict:
        name = (data.name or "").strip()
        if not name:
            raise ValidationError("Investment needs a name")
        kind = (data.kind or "other").strip().lower()
        if kind not in INVESTMENT_KINDS:
            raise ValidationError(f"Unknown investment kind: {kind}")
        # Values can legitimately be zero for a not-yet-started SIP, but
        # negative amounts are always a mistake.
        for label, value in (
            ("amount invested", data.amount_invested),
            ("current value", data.current_value),
            ("monthly contribution", data.monthly_contribution),
        ):
            if float(value or 0) < 0:
                raise ValidationError(f"{label.capitalize()} can't be negative")
        return {
            "name": name,
            "kind": kind,
            "institution": (data.institution or "").strip(),
            "amount_invested": float(data.amount_invested or 0),
            "current_value": float(data.current_value or 0),
            "annual_return_pct": float(data.annual_return_pct or 0),
            "monthly_contribution": float(data.monthly_contribution or 0),
            "start_date": (data.start_date or "").strip(),
            "maturity_date": (data.maturity_date or "").strip(),
            "notes": (data.notes or "").strip(),
        }
