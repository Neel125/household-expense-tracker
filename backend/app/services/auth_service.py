"""Registration, login, and household invites."""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models import Category, Household, Invite, Member, User
from app.models.mixins import now_iso
from app.repositories.repositories import (
    HouseholdRepo,
    InviteRepository,
    MemberRepository,
    UserRepository,
)
from app.services.defaults import DEFAULT_CATEGORIES
from app.services.errors import AuthError, ConflictError, NotFoundError, ValidationError


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.households = HouseholdRepo(session)
        self.invites = InviteRepository(session)
        self.members = MemberRepository(session)

    # ---- registration / login -------------------------------------------
    def register(
        self,
        email: str,
        password: str,
        display_name: str,
        household_name: str,
        referral_code: str = "",
    ) -> User:
        email = (email or "").strip()
        display_name = (display_name or "").strip()
        if not email or not password:
            raise ValidationError("Email and password are required")
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters")
        if self.users.find_by_email(email):
            raise ConflictError("An account with that email already exists")

        now = now_iso()
        household = self.households.add(
            Household(
                name=(household_name or f"{display_name or 'My'} household").strip(),
                created_at=now,
            )
        )
        self._seed_household(household.id, now)

        name_hint = display_name or email.split("@")[0]
        member = self.members.add(
            Member(
                household_id=household.id,
                name=name_hint,
                relation="Self",
                created_at=now,
            )
        )
        user = self.users.add(
            User(
                email=email,
                password_hash=hash_password(password),
                display_name=display_name,
                household_id=household.id,
                role="owner",
                member_id=member.id,
                created_at=now,
            )
        )

        # A referral code is a bonus, never a gate: an unknown or
        # self-referring code attaches nothing and the signup still
        # succeeds. Nothing is paid here — the referral starts `pending`
        # and only earns once the new household has actually been used.
        if referral_code:
            from app.services.referral_service import ReferralService

            ReferralService(self.session).attach(
                referral_code, household.id, user.id, display_name or name_hint
            )
        return user

    def login(self, email: str, password: str) -> User:
        user = self.users.find_by_email((email or "").strip())
        if not user or not verify_password(password, user.password_hash):
            raise AuthError("Wrong email or password")
        return user

    def token_for(self, user: User) -> str:
        return create_access_token(user.id, {"hid": user.household_id})

    # ---- profile ---------------------------------------------------------
    # 1 MB after base64 overhead — plenty for a tiny avatar, small enough
    # that pushing it through a JSON body isn't a footgun.
    AVATAR_MAX_BYTES = 1_400_000

    def update_profile(
        self,
        user: User,
        display_name: Optional[str] = None,
        contact_number: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> User:
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise ValidationError("Display name cannot be empty")
            user.display_name = name
            # Keep the linked member's display name in sync so the whole app
            # sees the change without a second write.
            if user.member_id:
                m = self.session.get(Member, user.member_id)
                if m:
                    m.name = name
                    self.session.add(m)

        if contact_number is not None:
            user.contact_number = contact_number.strip()

        if avatar_url is not None:
            av = avatar_url.strip()
            if av and not av.startswith(("data:image/", "http://", "https://", "")):
                raise ValidationError("Avatar must be an image data URL or a public URL")
            if len(av) > self.AVATAR_MAX_BYTES:
                raise ValidationError("Profile picture is too large (max ~1 MB after encoding)")
            user.avatar_url = av

        user.updated_at = now_iso()
        return self.users.save(user)

    # ---- invites ----------------------------------------------------------
    def create_invite(self, household_id: int, email: str, relation: str, invited_by: str) -> Invite:
        expires = datetime.now(timezone.utc) + timedelta(days=settings.invite_expire_days)
        return self.invites.add(
            Invite(
                token=secrets.token_urlsafe(24),
                household_id=household_id,
                email=(email or "").strip(),
                relation=(relation or "").strip(),
                invited_by=invited_by,
                expires_at=expires.isoformat(),
                created_at=now_iso(),
            )
        )

    def list_invites(self, household_id: int):
        return self.invites.list(household_id)

    def preview_invite(self, token: str):
        invite = self.invites.find_by_token(token)
        if not invite:
            return None, False
        household = self.households.get(invite.household_id)
        valid = invite.accepted_at is None and not self._expired(invite)
        return household, valid, invite

    def accept_invite(self, token: str, email: str, password: str, display_name: str, relation: str) -> User:
        invite = self.invites.find_by_token(token)
        if not invite:
            raise NotFoundError("This invite link is not valid")
        if invite.accepted_at is not None:
            raise ConflictError("This invite has already been used")
        if self._expired(invite):
            raise ConflictError("This invite link has expired")

        email = (email or "").strip()
        display_name = (display_name or "").strip()
        if not email or not password:
            raise ValidationError("Email and password are required")
        if len(password) < 6:
            raise ValidationError("Password must be at least 6 characters")
        if self.users.find_by_email(email):
            raise ConflictError("An account with that email already exists")

        now = now_iso()
        name = display_name or email.split("@")[0]
        if self.members.find_by_name(invite.household_id, name):
            name = f"{name} ({email.split('@')[0]})"
        member = self.members.add(
            Member(
                household_id=invite.household_id,
                name=name,
                relation=(relation or invite.relation or "").strip(),
                created_at=now,
            )
        )
        user = self.users.add(
            User(
                email=email,
                password_hash=hash_password(password),
                display_name=display_name,
                household_id=invite.household_id,
                role="member",
                member_id=member.id,
                created_at=now,
            )
        )
        invite.accepted_at = now
        self.invites.save(invite)
        return user

    # ---- helpers ----------------------------------------------------------
    def _seed_household(self, household_id: int, now: str) -> None:
        for i, (name, color) in enumerate(DEFAULT_CATEGORIES):
            self.session.add(
                Category(
                    household_id=household_id,
                    name=name,
                    color=color,
                    is_custom=False,
                    sort_order=i,
                    created_at=now,
                )
            )
        self.session.commit()

    @staticmethod
    def _expired(invite: Invite) -> bool:
        try:
            return datetime.fromisoformat(invite.expires_at) < datetime.now(timezone.utc)
        except (ValueError, TypeError):
            return False
