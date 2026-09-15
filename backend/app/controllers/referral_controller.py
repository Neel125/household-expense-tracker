from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.schemas.referral import (
    JoinedThroughOut,
    ReferralPreviewOut,
    ReferralRowOut,
    ReferralSummaryOut,
)
from app.services import reward_rules
from app.services.referral_service import ReferralService
from app.services.rewards_service import RewardsService

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.get("", response_model=ReferralSummaryOut)
def get_referrals(user: CurrentUser, session: SessionDep) -> ReferralSummaryOut:
    """This household's code, everyone it has brought in, and how close
    each of them is to earning both sides a payout."""
    service = ReferralService(session)
    rewards = RewardsService(session)
    # Reading settles first, so a friend who qualified since the last look
    # shows as paid rather than as still pending.
    rewards.settle(user.household_id, user.id)

    rows = service.made_by(user.household_id)
    joined = service.joined_through(user.household_id)
    totals = rewards.ledger.totals_by_kind(user.household_id)

    return ReferralSummaryOut(
        code=service.code_for(user.household_id),
        share_path="/register",
        reward_coins=reward_rules.coins_for("REFERRAL_QUALIFIED"),
        welcome_coins=reward_rules.coins_for("REFERRAL_WELCOME"),
        needed_expenses=reward_rules.REFERRAL_MIN_EXPENSES,
        needed_days=reward_rules.REFERRAL_MIN_ACTIVE_DAYS,
        monthly_cap=reward_rules.REFERRAL_MONTHLY_CAP,
        qualified_count=sum(1 for r, _ in rows if r.status == "qualified"),
        pending_count=sum(1 for r, _ in rows if r.status != "qualified"),
        coins_earned=totals.get("REFERRAL_QUALIFIED", 0),
        referrals=[ReferralRowOut.of(r, p) for r, p in rows],
        joined_through=(
            JoinedThroughOut(
                referrer_name=service.referrer_name(joined[0]),
                status=joined[0].status,
                pct=joined[1].pct,
                expenses=joined[1].expenses,
                active_days=joined[1].active_days,
                needed_expenses=joined[1].needed_expenses,
                needed_days=joined[1].needed_days,
                welcome_coins=reward_rules.coins_for("REFERRAL_WELCOME"),
            )
            if joined
            else None
        ),
    )


@router.get("/preview/{code}", response_model=ReferralPreviewOut)
def preview_referral(code: str, session: SessionDep) -> ReferralPreviewOut:
    """Public: lets the sign-up screen say who invited you. Unauthenticated
    by necessity — the visitor has no account yet — and deliberately thin,
    returning only a household name so a code cannot be used to enumerate
    anything worth having."""
    household = ReferralService(session).preview(code)
    if not household:
        return ReferralPreviewOut(valid=False)
    return ReferralPreviewOut(
        valid=True,
        household_name=household.name,
        welcome_coins=reward_rules.coins_for("REFERRAL_WELCOME"),
        needed_expenses=reward_rules.REFERRAL_MIN_EXPENSES,
        needed_days=reward_rules.REFERRAL_MIN_ACTIVE_DAYS,
    )
