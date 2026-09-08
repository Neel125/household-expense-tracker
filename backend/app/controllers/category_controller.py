from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.category import CategoryIn, CategoryOut
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(user: CurrentUser, session: SessionDep) -> list[CategoryOut]:
    service = CategoryService(session)
    return [CategoryOut.model_validate(c) for c in service.list(user.household_id)]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryIn, user: CurrentUser, session: SessionDep) -> CategoryOut:
    service = CategoryService(session)
    return CategoryOut.model_validate(service.create(user.household_id, payload))


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, payload: CategoryIn, user: CurrentUser, session: SessionDep) -> CategoryOut:
    service = CategoryService(session)
    return CategoryOut.model_validate(service.update(user.household_id, category_id, payload))


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: int, user: CurrentUser, session: SessionDep) -> Response:
    CategoryService(session).delete(user.household_id, category_id)
    return Response(status_code=204)
