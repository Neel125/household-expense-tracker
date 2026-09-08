"""Family members. Transactions reference a member by name, so a rename
cascades and a delete makes the caller decide where history goes."""
from typing import Optional

from sqlmodel import Session

from app.models import Member
from app.models.mixins import now_iso
from app.repositories.repositories import MemberRepository, TransactionRepository
from app.schemas.member import MemberIn
from app.services.errors import ConflictError, NotFoundError, ValidationError


class MemberService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.members = MemberRepository(session)
        self.transactions = TransactionRepository(session)

    def list(self, household_id: int):
        return self.members.list(household_id)

    def create(self, household_id: int, data: MemberIn) -> Member:
        name = data.name.strip()
        if not name:
            raise ValidationError("A member needs a name")
        if self.members.find_by_name(household_id, name):
            raise ConflictError(f"{name} is already a family member")
        return self.members.add(
            Member(
                household_id=household_id,
                name=name,
                relation=data.relation.strip(),
                monthly_budget=max(0.0, float(data.monthly_budget or 0)),
                created_at=now_iso(),
            )
        )

    def update(self, household_id: int, member_id: int, data: MemberIn) -> Member:
        name = data.name.strip()
        if not name:
            raise ValidationError("A member needs a name")
        member = self.members.get(household_id, member_id)
        if not member:
            raise NotFoundError("Member not found")

        clash = self.members.find_by_name(household_id, name)
        if clash and clash.id != member.id:
            raise ConflictError(f"{name} is already a family member")

        old_name = member.name
        member.name = name
        member.relation = data.relation.strip()
        member.monthly_budget = max(0.0, float(data.monthly_budget or 0))
        member.updated_at = now_iso()

        if old_name != name:
            for t in self.transactions.for_member(household_id, old_name):
                t.member = name
                t.updated_at = member.updated_at
                self.session.add(t)
        return self.members.save(member)

    def delete(self, household_id: int, member_id: int, reassign_to: Optional[str]) -> dict:
        member = self.members.get(household_id, member_id)
        if not member:
            raise NotFoundError("Member not found")

        theirs = list(self.transactions.for_member(household_id, member.name))
        if theirs and reassign_to is None:
            raise ConflictError(
                f"{member.name} has {len(theirs)} transaction(s). Choose someone to "
                f"move them to, or untag them, before removing {member.name}."
            )

        target = ""
        if theirs and reassign_to:
            other = self.members.find_by_name(household_id, reassign_to)
            if not other or other.id == member.id:
                raise ValidationError(
                    f"No family member named {reassign_to} to move the transactions to"
                )
            target = other.name

        now = now_iso()
        for t in theirs:
            t.member = target
            t.updated_at = now
            self.session.add(t)
        self.session.commit()
        self.members.delete(member)
        return {"deleted": member.name, "transactionsMoved": len(theirs), "movedTo": target}
