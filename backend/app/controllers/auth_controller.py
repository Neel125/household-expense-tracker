from fastapi import APIRouter

from app.core.deps import CurrentUser, OwnerUser, SessionDep
from app.repositories.repositories import HouseholdRepo
from app.schemas.auth import (
    AcceptInviteIn,
    AuthOut,
    HouseholdOut,
    InviteIn,
    InviteOut,
    InvitePreview,
    LoginIn,
    ProfileUpdateIn,
    RegisterIn,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_out(service: AuthService, user) -> AuthOut:
    household = service.households.get(user.household_id)
    return AuthOut(
        token=service.token_for(user),
        user=UserOut.model_validate(user),
        household=HouseholdOut.model_validate(household),
    )


@router.post("/register", response_model=AuthOut, status_code=201)
def register(payload: RegisterIn, session: SessionDep) -> AuthOut:
    service = AuthService(session)
    user = service.register(
        payload.email,
        payload.password,
        payload.display_name,
        payload.household_name,
        payload.referral_code,
    )
    return _auth_out(service, user)


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, session: SessionDep) -> AuthOut:
    service = AuthService(session)
    user = service.login(payload.email, payload.password)
    return _auth_out(service, user)


@router.get("/me", response_model=AuthOut)
def me(user: CurrentUser, session: SessionDep) -> AuthOut:
    service = AuthService(session)
    return _auth_out(service, user)


@router.patch("/me", response_model=AuthOut)
def update_me(
    payload: ProfileUpdateIn, user: CurrentUser, session: SessionDep
) -> AuthOut:
    service = AuthService(session)
    user = service.update_profile(
        user,
        display_name=payload.display_name,
        contact_number=payload.contact_number,
        avatar_url=payload.avatar_url,
    )
    return _auth_out(service, user)


@router.get("/invites", response_model=list[InviteOut])
def list_invites(user: CurrentUser, session: SessionDep) -> list[InviteOut]:
    service = AuthService(session)
    return [InviteOut.model_validate(i) for i in service.list_invites(user.household_id)]


@router.post("/invites", response_model=InviteOut, status_code=201)
def create_invite(payload: InviteIn, user: OwnerUser, session: SessionDep) -> InviteOut:
    service = AuthService(session)
    invite = service.create_invite(
        user.household_id, payload.email, payload.relation, user.display_name
    )
    return InviteOut.model_validate(invite)


@router.get("/invites/{token}/preview", response_model=InvitePreview)
def preview_invite(token: str, session: SessionDep) -> InvitePreview:
    service = AuthService(session)
    result = service.preview_invite(token)
    if result[0] is None:
        return InvitePreview(household_name="", relation="", valid=False)
    household, valid, invite = result
    return InvitePreview(
        household_name=household.name if household else "",
        relation=invite.relation,
        valid=valid,
    )


@router.post("/accept-invite", response_model=AuthOut, status_code=201)
def accept_invite(payload: AcceptInviteIn, session: SessionDep) -> AuthOut:
    service = AuthService(session)
    user = service.accept_invite(
        payload.token,
        payload.email,
        payload.password,
        payload.display_name,
        payload.relation,
    )
    return _auth_out(service, user)
