from typing import Optional

from pydantic import EmailStr

from app.schemas.base import CamelModel


class RegisterIn(CamelModel):
    email: EmailStr
    password: str
    display_name: str
    household_name: str = ""
    # Optional "refer a friend" code. Unknown codes are ignored rather
    # than rejected — a bad code must never cost someone their signup.
    referral_code: str = ""


class LoginIn(CamelModel):
    email: EmailStr
    password: str


class AcceptInviteIn(CamelModel):
    token: str
    email: EmailStr
    password: str
    display_name: str
    relation: str = ""


class UserOut(CamelModel):
    id: int
    email: str
    display_name: str
    contact_number: str = ""
    avatar_url: str = ""
    household_id: int
    role: str
    member_id: Optional[int] = None


class ProfileUpdateIn(CamelModel):
    display_name: Optional[str] = None
    contact_number: Optional[str] = None
    avatar_url: Optional[str] = None


class HouseholdOut(CamelModel):
    id: int
    name: str
    monthly_budget: float


class AuthOut(CamelModel):
    token: str
    user: UserOut
    household: HouseholdOut


class InviteIn(CamelModel):
    email: str = ""
    relation: str = ""


class InviteOut(CamelModel):
    id: int
    token: str
    email: str
    relation: str
    expires_at: str
    accepted_at: Optional[str] = None
    created_at: str


class InvitePreview(CamelModel):
    household_name: str
    relation: str = ""
    valid: bool
