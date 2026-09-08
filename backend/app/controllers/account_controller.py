from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.account import AccountIn, AccountOut
from app.services.account_service import AccountService

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(user: CurrentUser, session: SessionDep) -> list[AccountOut]:
    service = AccountService(session)
    return [AccountOut.model_validate(a) for a in service.list(user.household_id)]


@router.post("", response_model=AccountOut, status_code=201)
def create_account(payload: AccountIn, user: CurrentUser, session: SessionDep) -> AccountOut:
    service = AccountService(session)
    return AccountOut.model_validate(service.create(user.household_id, payload))


@router.put("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, payload: AccountIn, user: CurrentUser, session: SessionDep) -> AccountOut:
    service = AccountService(session)
    return AccountOut.model_validate(service.update(user.household_id, account_id, payload))


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: int, user: CurrentUser, session: SessionDep) -> Response:
    AccountService(session).delete(user.household_id, account_id)
    return Response(status_code=204)
