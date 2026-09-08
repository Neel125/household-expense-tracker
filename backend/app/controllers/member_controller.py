from typing import Optional

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, SessionDep
from app.schemas.member import MemberIn, MemberOut
from app.services.member_service import MemberService

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
def list_members(user: CurrentUser, session: SessionDep) -> list[MemberOut]:
    service = MemberService(session)
    return [MemberOut.model_validate(m) for m in service.list(user.household_id)]


@router.post("", response_model=MemberOut, status_code=201)
def create_member(payload: MemberIn, user: CurrentUser, session: SessionDep) -> MemberOut:
    service = MemberService(session)
    return MemberOut.model_validate(service.create(user.household_id, payload))


@router.put("/{member_id}", response_model=MemberOut)
def update_member(member_id: int, payload: MemberIn, user: CurrentUser, session: SessionDep) -> MemberOut:
    service = MemberService(session)
    return MemberOut.model_validate(service.update(user.household_id, member_id, payload))


@router.delete("/{member_id}")
def delete_member(
    member_id: int,
    user: CurrentUser,
    session: SessionDep,
    reassign_to: Optional[str] = Query(
        None,
        description="Member to move this person's transactions to. Required when "
        "they have any; pass an empty string to untag them instead.",
    ),
) -> dict:
    service = MemberService(session)
    return service.delete(user.household_id, member_id, reassign_to)
