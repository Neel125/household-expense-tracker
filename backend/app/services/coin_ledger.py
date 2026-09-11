"""The coin ledger: the only thing allowed to write coins.

Three invariants live here, and nowhere else:

1. **The ledger is the source of truth.** No `household.coins` column
   exists; the balance is SUM(amount) over the rows. Reads stay cheap
   because the row count per household is small (one row per rewarded
   event, capped per day) — if that ever stops being true, a balance
   projection can be added *alongside* the ledger without touching a
   single caller of this class.
2. **Every event pays at most once.** Callers supply an `event_key` that
   identifies the real-world event, and a unique index enforces it. A
   retried request, a double-click, two workers — all land on the same
   key and only one row.
3. **Nothing is edited or deleted.** An undone action gets a
   compensating negative row, so the history explains the balance.

On top of those sit the anti-farming limits from the design review: a
per-rule daily cap and reversal on delete. Judging whether the *activity*
looks automated needs the transactions themselves, so that check lives in
RewardsService and arrives here as `flag`.
"""
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import CoinTransaction
from app.models.mixins import now_iso
from app.repositories.repositories import CoinTransactionRepository
from app.services import reward_rules
from app.services.reward_rules import RULES


def _start_of_day_iso() -> str:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


class CoinLedger:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.coins = CoinTransactionRepository(session)

    # ------------------------------------------------------------- reads
    def balance(self, household_id: int) -> int:
        return self.coins.balance(household_id)

    def history(self, household_id: int, limit: int = 50) -> Sequence[CoinTransaction]:
        return self.coins.history(household_id, limit)

    def totals_by_kind(self, household_id: int) -> dict[str, int]:
        return self.coins.totals_by_kind(household_id)

    def already_awarded(self, household_id: int, event_key: str) -> bool:
        return self.find(household_id, event_key) is not None

    def find(self, household_id: int, event_key: str) -> Optional[CoinTransaction]:
        return self.coins.find_by_event_key(household_id, event_key)

    def earned_today(self, household_id: int, kind: str) -> int:
        """Coins one rule has paid so far today. Days here are UTC days,
        matching the `created_at` stamps the cap is measured against."""
        return self.coins.earned_for_kind_since(household_id, kind, _start_of_day_iso())

    # ------------------------------------------------------------ writes
    def award(
        self,
        household_id: int,
        kind: str,
        event_key: str,
        *,
        user_id: Optional[int] = None,
        coins: Optional[int] = None,
        reference_type: str = "",
        reference_id: str = "",
        note: str = "",
    ) -> Optional[CoinTransaction]:
        """Credit coins for one event, or return None if it earns nothing.

        None is the normal, uninteresting answer: the event was already
        paid, the rule's daily cap is spent, or the activity looks
        automated. Callers fire and forget.
        """
        payout = reward_rules.coins_for(kind) if coins is None else int(coins)
        if payout <= 0:
            return None

        # (2) Idempotency, checked before anything else.
        if self.already_awarded(household_id, event_key):
            return None

        rule = RULES.get(kind)
        if rule and rule.daily_cap is not None:
            # Daily cap. Reversals are their own rule, so a
            # create/delete loop still burns through today's cap — the
            # farm loop nets zero coins *and* uses up the allowance.
            earned_today = self.coins.earned_for_kind_since(household_id, kind, _start_of_day_iso())
            remaining = rule.daily_cap - earned_today
            if remaining <= 0:
                self._flag(
                    household_id,
                    f"cap:{kind}:{_start_of_day_iso()[:10]}",
                    note=f"Daily limit of {rule.daily_cap} coins for "
                    f"{reward_rules.label_for(kind).lower()} reached",
                    user_id=user_id,
                )
                return None
            payout = min(payout, remaining)

        return self._insert(
            household_id,
            kind=kind,
            amount=payout,
            event_key=event_key,
            user_id=user_id,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note or reward_rules.label_for(kind),
        )

    def reverse(
        self,
        household_id: int,
        awarded_event_key: str,
        *,
        kind: str,
        note: str = "",
    ) -> Optional[CoinTransaction]:
        """Undo an award by writing its mirror image.

        Used when a rewarded action is taken back — deleting a logged
        expense claws its coin back. If the original never paid (capped,
        flagged, or already reversed) there is nothing to mirror.
        """
        original = self.coins.find_by_event_key(household_id, awarded_event_key)
        if original is None or original.amount <= 0:
            return None
        return self._insert(
            household_id,
            kind=kind,
            amount=-original.amount,
            event_key=f"{kind}:{awarded_event_key}",
            user_id=original.user_id,
            reference_type=original.reference_type,
            reference_id=original.reference_id,
            note=note or reward_rules.label_for(kind),
        )

    def flag(self, household_id: int, suffix: str, *, note: str, user_id: Optional[int] = None) -> None:
        """Record, once, that an award was withheld — for a reason the
        ledger itself can't see, such as activity that looks automated.
        Callers key `suffix` so repeated attempts collapse into one row."""
        self._flag(household_id, suffix, note=note, user_id=user_id)

    # ------------------------------------------------------------ internals
    def _flag(self, household_id: int, suffix: str, *, note: str, user_id: Optional[int]) -> None:
        """Record, once, that an award was withheld. Zero coins."""
        self._insert(
            household_id,
            kind=reward_rules.FLAGGED,
            amount=0,
            event_key=f"{reward_rules.FLAGGED}:{suffix}",
            user_id=user_id,
            reference_type="",
            reference_id="",
            note=note,
        )

    def _insert(
        self,
        household_id: int,
        *,
        kind: str,
        amount: int,
        event_key: str,
        user_id: Optional[int],
        reference_type: str,
        reference_id: str,
        note: str,
    ) -> Optional[CoinTransaction]:
        row = CoinTransaction(
            household_id=household_id,
            user_id=user_id,
            kind=kind,
            amount=amount,
            event_key=event_key,
            reference_type=reference_type,
            reference_id=reference_id,
            note=note,
            created_at=now_iso(),
        )
        self.session.add(row)
        try:
            self.session.commit()
        except IntegrityError:
            # The unique index caught a race the pre-check missed: two
            # requests awarding the same event at once. The event is paid
            # either way, so this is success, not failure. Rolling back is
            # safe because every service in this app commits its own write
            # before events are published.
            self.session.rollback()
            return None
        self.session.refresh(row)
        return row
