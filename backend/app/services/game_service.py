"""Play-and-earn games: quiz, puzzle, spin-the-wheel.

The client animates; this service is the only thing allowed to decide
whether a round paid and how much. Questions for a given household+day
are derived from a seeded RNG so a refresh doesn't swap the paper, and
payouts are rolled only after a pass so you cannot probe the range.

One attempt per game per local day. A miss still writes a zero-coin
flagged row, which consumes the attempt without paying.
"""
from __future__ import annotations

import hashlib
import random
import secrets
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlmodel import Session

from app.services import game_rules, reward_rules
from app.services.coin_ledger import CoinLedger
from app.services.errors import ValidationError
from app.services.game_rules import (
    GAMES,
    GAMES_BY_KEY,
    KIND_PUZZLE,
    KIND_QUIZ,
    KIND_SPIN,
    PUZZLE_BANK,
    QUIZ_BANK,
    QUIZ_PASS_SCORE,
    QUIZ_QUESTION_COUNT,
    WHEEL_SLICES,
    GameDef,
    Puzzle,
    QuizQuestion,
)


def _today() -> str:
    return date.today().isoformat()


def _rng(household_id: int, salt: str) -> random.Random:
    """Stable per household per day so the same quiz/puzzle comes back
    if they close the modal and reopen it."""
    material = f"{household_id}:{_today()}:{salt}".encode()
    seed = int(hashlib.sha256(material).hexdigest()[:16], 16)
    return random.Random(seed)


@dataclass
class GameStatus:
    key: str
    title: str
    description: str
    icon: str
    payout_min: int
    payout_max: int
    hint: str
    played: bool
    passed: bool
    coins_awarded: int


@dataclass
class GameResult:
    key: str
    played: bool
    passed: bool
    coins: int
    message: str
    score: Optional[int] = None
    target: Optional[int] = None
    segment_index: Optional[int] = None
    balance: int = 0


@dataclass
class QuizRound:
    played: bool
    passed: bool
    coins_awarded: int
    pass_score: int
    questions: list[QuizQuestion] = field(default_factory=list)


@dataclass
class PuzzleRound:
    played: bool
    passed: bool
    coins_awarded: int
    puzzle_id: str
    kind: str
    title: str
    prompt: str
    items: list[dict[str, str]]
    options: list[str]


class GameService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.ledger = CoinLedger(session)

    # -------------------------------------------------------------- status
    def statuses(self, household_id: int) -> list[GameStatus]:
        return [self._status(household_id, g) for g in GAMES]

    def _status(self, household_id: int, game: GameDef) -> GameStatus:
        award = self.ledger.find(household_id, self._award_key(game.key))
        flagged = self.ledger.already_awarded(household_id, self._flag_key(game.key))
        played = award is not None or flagged
        coins = award.amount if award else 0
        return GameStatus(
            key=game.key,
            title=game.title,
            description=game.description,
            icon=game.icon,
            payout_min=game.payout_min,
            payout_max=game.payout_max,
            hint=game.hint,
            played=played,
            passed=bool(award and award.amount > 0),
            coins_awarded=coins,
        )

    # ---------------------------------------------------------------- quiz
    def quiz_round(self, household_id: int) -> QuizRound:
        status = self._status(household_id, GAMES_BY_KEY[KIND_QUIZ])
        questions = [] if status.played else self._todays_quiz(household_id)
        return QuizRound(
            played=status.played,
            passed=status.passed,
            coins_awarded=status.coins_awarded,
            pass_score=QUIZ_PASS_SCORE,
            questions=questions,
        )

    def submit_quiz(
        self, household_id: int, user_id: Optional[int], answers: list[dict[str, Any]]
    ) -> GameResult:
        self._guard_fresh(household_id, KIND_QUIZ)
        paper = {q.id: q for q in self._todays_quiz(household_id)}
        if len(answers) != len(paper):
            raise ValidationError(f"Answer all {len(paper)} questions")
        score = 0
        seen: set[str] = set()
        for row in answers:
            qid = str(row.get("id") or "")
            if qid in seen or qid not in paper:
                raise ValidationError("Those aren't today's questions")
            seen.add(qid)
            try:
                choice = int(row.get("choice"))
            except (TypeError, ValueError):
                raise ValidationError("Each answer needs a choice") from None
            if choice == paper[qid].correct:
                score += 1
        passed = score >= QUIZ_PASS_SCORE
        coins = self._payout(KIND_QUIZ) if passed else 0
        return self._settle(
            household_id,
            user_id,
            KIND_QUIZ,
            passed=passed,
            coins=coins,
            score=score,
            target=QUIZ_PASS_SCORE,
            note=(
                f"Quiz {score}/{len(paper)} — won {coins} coins"
                if passed
                else f"Quiz {score}/{len(paper)} — needed {QUIZ_PASS_SCORE} to win"
            ),
            fail_note=f"Quiz attempted, scored {score}/{len(paper)}",
        )

    def _todays_quiz(self, household_id: int) -> list[QuizQuestion]:
        rng = _rng(household_id, "quiz")
        return rng.sample(list(QUIZ_BANK), QUIZ_QUESTION_COUNT)

    # -------------------------------------------------------------- puzzle
    def puzzle_round(self, household_id: int) -> PuzzleRound:
        status = self._status(household_id, GAMES_BY_KEY[KIND_PUZZLE])
        puzzle = self._todays_puzzle(household_id)
        items: list[dict[str, str]] = []
        options: list[str] = list(puzzle.options)
        if puzzle.kind == "sorter":
            items = [{"id": i.id, "label": i.label} for i in puzzle.items]
        elif puzzle.kind == "match":
            items = [{"id": i.id, "term": i.term} for i in puzzle.items]
            options = [i.definition for i in puzzle.items]
            rng = _rng(household_id, f"match:{puzzle.id}")
            rng.shuffle(options)
        elif puzzle.kind == "riddle":
            options = list(puzzle.options)
        return PuzzleRound(
            played=status.played,
            passed=status.passed,
            coins_awarded=status.coins_awarded,
            puzzle_id=puzzle.id,
            kind=puzzle.kind,
            title=puzzle.title,
            prompt=puzzle.prompt,
            items=items,
            options=options,
        )

    def submit_puzzle(
        self, household_id: int, user_id: Optional[int], payload: dict[str, Any]
    ) -> GameResult:
        self._guard_fresh(household_id, KIND_PUZZLE)
        puzzle = self._todays_puzzle(household_id)
        if (payload.get("id") or "") != puzzle.id:
            raise ValidationError("That's not today's puzzle")
        passed = self._score_puzzle(puzzle, payload)
        coins = self._payout(KIND_PUZZLE) if passed else 0
        return self._settle(
            household_id,
            user_id,
            KIND_PUZZLE,
            passed=passed,
            coins=coins,
            score=1 if passed else 0,
            target=1,
            note=f"Solved “{puzzle.title}” — won {coins} coins" if passed else f"Missed “{puzzle.title}”",
            fail_note=f"Puzzle attempted: {puzzle.title}",
        )

    def _todays_puzzle(self, household_id: int) -> Puzzle:
        rng = _rng(household_id, "puzzle")
        return rng.choice(list(PUZZLE_BANK))

    @staticmethod
    def _score_puzzle(puzzle: Puzzle, payload: dict[str, Any]) -> bool:
        if puzzle.kind == "riddle":
            try:
                return int(payload.get("choice")) == puzzle.correct
            except (TypeError, ValueError):
                return False
        answers = payload.get("answers") or {}
        if not isinstance(answers, dict):
            return False
        if puzzle.kind == "sorter":
            if len(answers) != len(puzzle.items):
                return False
            return all(
                str(answers.get(item.id) or "").strip().lower() == item.bucket
                for item in puzzle.items
            )
        if puzzle.kind == "match":
            if len(answers) != len(puzzle.items):
                return False
            return all(
                str(answers.get(pair.id) or "") == pair.definition for pair in puzzle.items
            )
        return False

    # ---------------------------------------------------------------- spin
    def spin(self, household_id: int, user_id: Optional[int]) -> GameResult:
        existing = self._existing_result(household_id, KIND_SPIN)
        if existing:
            return existing
        index = secrets.randbelow(len(WHEEL_SLICES))
        slice_ = WHEEL_SLICES[index]
        return self._settle(
            household_id,
            user_id,
            KIND_SPIN,
            passed=True,
            coins=slice_.coins,
            score=None,
            target=None,
            note=f"Wheel landed on {slice_.coins} coins",
            fail_note="",
            segment_index=index,
        )

    # ---------------------------------------------------------- internals
    def _guard_fresh(self, household_id: int, kind: str) -> None:
        if self._status(household_id, GAMES_BY_KEY[kind]).played:
            raise ValidationError("That's already been played today — come back tomorrow")

    def _existing_result(self, household_id: int, kind: str) -> Optional[GameResult]:
        status = self._status(household_id, GAMES_BY_KEY[kind])
        if not status.played:
            return None
        return GameResult(
            key=kind,
            played=True,
            passed=status.passed,
            coins=status.coins_awarded,
            message="Already played today",
            balance=self.ledger.balance(household_id),
        )

    def _payout(self, kind: str) -> int:
        game = GAMES_BY_KEY[kind]
        # secrets, not the seeded RNG — the paper is predictable for the
        # day, the prize is not.
        span = game.payout_max - game.payout_min + 1
        return game.payout_min + secrets.randbelow(span)

    def _settle(
        self,
        household_id: int,
        user_id: Optional[int],
        kind: str,
        *,
        passed: bool,
        coins: int,
        score: Optional[int],
        target: Optional[int],
        note: str,
        fail_note: str,
        segment_index: Optional[int] = None,
    ) -> GameResult:
        if passed and coins > 0:
            self.ledger.award(
                household_id,
                kind,
                self._award_key(kind),
                user_id=user_id,
                coins=coins,
                reference_type="game",
                reference_id=_today(),
                note=note,
            )
        else:
            self.ledger.flag(
                household_id,
                f"{kind}:{_today()}",
                note=fail_note or note,
                user_id=user_id,
            )
        return GameResult(
            key=kind,
            played=True,
            passed=passed,
            coins=coins if passed else 0,
            message=note,
            score=score,
            target=target,
            segment_index=segment_index,
            balance=self.ledger.balance(household_id),
        )

    @staticmethod
    def _award_key(kind: str) -> str:
        return f"{kind}:{_today()}"

    @staticmethod
    def _flag_key(kind: str) -> str:
        return f"{reward_rules.FLAGGED}:{kind}:{_today()}"
