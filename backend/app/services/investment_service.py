"""Household investments (FD/RD/SIP/stocks/etc.).

Beyond simple CRUD, this service is where the "investment" domain
publishes the two facts the rewards engine listens for: a new investment
was tracked, and an existing one hit its maturity date. The service
itself never awards coins — it only fires the event, keeping the reward
catalogue as the single source of truth for how much anything is worth.
"""
from datetime import date
from typing import Optional

from sqlmodel import Session

from app.models import Investment
from app.models.investment import INVESTMENT_KINDS
from app.models.mixins import now_iso
from app.repositories.repositories import InvestmentRepository
from app.schemas.investment import InvestmentIn
from app.services import events
from app.services.errors import NotFoundError, ValidationError


class InvestmentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.investments = InvestmentRepository(session)

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
