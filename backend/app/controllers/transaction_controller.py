from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.transaction import TransactionIn, TransactionOut
from app.services.transaction_service import TransactionService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(user: CurrentUser, session: SessionDep) -> list[TransactionOut]:
    service = TransactionService(session)
    return [TransactionOut.model_validate(t) for t in service.list(user.household_id)]


@router.post("", response_model=TransactionOut, status_code=201)
def create_transaction(payload: TransactionIn, user: CurrentUser, session: SessionDep) -> TransactionOut:
    service = TransactionService(session)
    return TransactionOut.model_validate(service.create(user.household_id, payload))


@router.put("/{txn_id}", response_model=TransactionOut)
def update_transaction(txn_id: int, payload: TransactionIn, user: CurrentUser, session: SessionDep) -> TransactionOut:
    service = TransactionService(session)
    return TransactionOut.model_validate(service.update(user.household_id, txn_id, payload))


@router.delete("/{txn_id}", status_code=204)
def delete_transaction(txn_id: int, user: CurrentUser, session: SessionDep) -> Response:
    TransactionService(session).delete(user.household_id, txn_id)
    return Response(status_code=204)
