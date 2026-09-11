from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep
from app.schemas.reward import (
    ChallengeOut,
    GameResultOut,
    HealthOut,
    PuzzleRoundOut,
    PuzzleSubmitIn,
    QuizRoundOut,
    QuizSubmitIn,
    ReviewIn,
    ReviewOut,
    RewardsSummaryOut,
    WheelRoundOut,
    WheelSliceOut,
)
from app.services.challenge_service import ChallengeService
from app.services.game_rules import WHEEL_SLICES
from app.services.game_service import GameService
from app.services.health_service import HealthService
from app.services.rewards_service import RewardsService

router = APIRouter(prefix="/rewards", tags=["rewards"])


@router.get("", response_model=RewardsSummaryOut)
def get_rewards(user: CurrentUser, session: SessionDep) -> RewardsSummaryOut:
    """Coins, level, streak, health score, challenges and recent ledger
    rows — one response, because that is one screen. Reading also settles
    anything the household has earned since the last look."""
    summary = RewardsService(session).summary(user.household_id, user.id)
    return RewardsSummaryOut.of(summary)


@router.get("/health", response_model=HealthOut)
def get_health(user: CurrentUser, session: SessionDep, month: str | None = None) -> HealthOut:
    return HealthOut.of(HealthService(session).report(user.household_id, month))


@router.post("/review", response_model=ReviewOut)
def record_review(payload: ReviewIn, user: CurrentUser, session: SessionDep) -> ReviewOut:
    service = RewardsService(session)
    awarded = service.record_review(user.household_id, user.id, payload.month)
    return ReviewOut(
        month=payload.month,
        coins_awarded=awarded,
        balance=service.ledger.balance(user.household_id),
    )


@router.post("/challenges/{challenge_key}/join", response_model=ChallengeOut, status_code=201)
def join_challenge(challenge_key: str, user: CurrentUser, session: SessionDep) -> ChallengeOut:
    state = ChallengeService(session).join(user.household_id, user.id, challenge_key)
    return ChallengeOut.of(state)


@router.delete("/challenges/{challenge_key}", status_code=204)
def leave_challenge(challenge_key: str, user: CurrentUser, session: SessionDep) -> Response:
    ChallengeService(session).leave(user.household_id, challenge_key)
    return Response(status_code=204)


@router.get("/games/quiz", response_model=QuizRoundOut)
def get_quiz(user: CurrentUser, session: SessionDep) -> QuizRoundOut:
    return QuizRoundOut.of(GameService(session).quiz_round(user.household_id))


@router.post("/games/quiz", response_model=GameResultOut)
def submit_quiz(
    payload: QuizSubmitIn, user: CurrentUser, session: SessionDep
) -> GameResultOut:
    answers = [a.model_dump() for a in payload.answers]
    result = GameService(session).submit_quiz(user.household_id, user.id, answers)
    return GameResultOut.of(result)


@router.get("/games/puzzle", response_model=PuzzleRoundOut)
def get_puzzle(user: CurrentUser, session: SessionDep) -> PuzzleRoundOut:
    return PuzzleRoundOut.of(GameService(session).puzzle_round(user.household_id))


@router.post("/games/puzzle", response_model=GameResultOut)
def submit_puzzle(
    payload: PuzzleSubmitIn, user: CurrentUser, session: SessionDep
) -> GameResultOut:
    result = GameService(session).submit_puzzle(
        user.household_id, user.id, payload.model_dump()
    )
    return GameResultOut.of(result)


@router.get("/games/wheel", response_model=WheelRoundOut)
def get_wheel(user: CurrentUser, session: SessionDep) -> WheelRoundOut:
    games = {g.key: g for g in GameService(session).statuses(user.household_id)}
    spin = games["GAME_SPIN"]
    return WheelRoundOut(
        played=spin.played,
        passed=spin.passed,
        coins_awarded=spin.coins_awarded,
        slices=[WheelSliceOut.model_validate(s) for s in WHEEL_SLICES],
    )


@router.post("/games/spin", response_model=GameResultOut)
def spin_wheel(user: CurrentUser, session: SessionDep) -> GameResultOut:
    return GameResultOut.of(GameService(session).spin(user.household_id, user.id))
