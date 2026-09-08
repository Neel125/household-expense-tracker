"""Rewards DTOs.

The Rewards page needs coins, level, streak, health, challenges and
history together — refetching six endpoints to draw one screen would be
worse than one composite response, so `RewardsSummaryOut.of` assembles
it. The mapping lives here rather than in the controller so the HTTP
layer stays a one-liner, as it is for every other resource.
"""
from typing import Optional

from app.schemas.base import CamelModel
from app.services import reward_rules
from app.services.challenge_service import ChallengeState
from app.services.health_service import HealthReport
from app.services.reward_rules import Level
from app.services.rewards_service import RewardsSummary, Streak


class LevelOut(CamelModel):
    number: int
    name: str
    icon: str
    min_coins: int
    perks: list[str] = []
    coins_to_go: int = 0

    @classmethod
    def of(cls, level: Level, balance: int) -> "LevelOut":
        return cls(
            number=level.number,
            name=level.name,
            icon=level.icon,
            min_coins=level.min_coins,
            perks=list(level.perks),
            coins_to_go=max(0, level.min_coins - balance),
        )


class StreakOut(CamelModel):
    days: int
    best: int
    logged_today: bool


class HealthComponentOut(CamelModel):
    key: str
    label: str
    score: Optional[int]
    detail: str


class HealthOut(CamelModel):
    month: str
    score: int
    components: list[HealthComponentOut]

    @classmethod
    def of(cls, report: HealthReport) -> "HealthOut":
        return cls(
            month=report.month,
            score=report.score,
            components=[HealthComponentOut.model_validate(c) for c in report.components],
        )


class CoinRowOut(CamelModel):
    id: int
    kind: str
    label: str
    amount: int
    note: str
    reference_type: str
    reference_id: str
    created_at: str


class BreakdownRowOut(CamelModel):
    kind: str
    label: str
    coins: int


class ChallengeOut(CamelModel):
    key: str
    title: str
    description: str
    icon: str
    coins: int
    period: str
    status: str  # available | active | completed | missed
    current: float
    target: float
    pct: int
    caption: str
    eligible: bool

    @classmethod
    def of(cls, state: ChallengeState) -> "ChallengeOut":
        c, o = state.challenge, state.outcome
        return cls(
            key=c.key,
            title=c.title,
            description=c.description,
            icon=c.icon,
            coins=c.coins,
            period=c.period,
            status=state.status,
            current=round(o.current, 2),
            target=round(o.target, 2),
            pct=o.pct,
            caption=o.caption,
            eligible=o.eligible,
        )


class EarnRuleOut(CamelModel):
    """A row of the "how to earn" table, straight from the catalogue so
    the UI can never disagree with what the engine pays."""

    kind: str
    label: str
    coins: int
    daily_cap: Optional[int] = None


class RewardsSummaryOut(CamelModel):
    balance: int
    earned_this_month: int
    level: LevelOut
    next_level: Optional[LevelOut]
    streak: StreakOut
    health: HealthOut
    breakdown: list[BreakdownRowOut]
    history: list[CoinRowOut]
    challenges: list[ChallengeOut]
    catalog: list[EarnRuleOut]
    daily_cap_remaining: int
    review_month: str
    review_claimed: bool

    @classmethod
    def of(cls, summary: RewardsSummary) -> "RewardsSummaryOut":
        return cls(
            balance=summary.balance,
            earned_this_month=summary.earned_this_month,
            level=LevelOut.of(summary.level, summary.balance),
            next_level=(
                LevelOut.of(summary.next_level, summary.balance) if summary.next_level else None
            ),
            streak=StreakOut.model_validate(summary.streak),
            health=HealthOut.of(summary.health),
            breakdown=[
                BreakdownRowOut(kind=kind, label=reward_rules.label_for(kind), coins=coins)
                for kind, coins in sorted(
                    summary.breakdown.items(), key=lambda kv: kv[1], reverse=True
                )
            ],
            history=[
                CoinRowOut(
                    id=row.id,
                    kind=row.kind,
                    label=reward_rules.label_for(row.kind),
                    amount=row.amount,
                    note=row.note,
                    reference_type=row.reference_type,
                    reference_id=row.reference_id,
                    created_at=row.created_at,
                )
                for row in summary.history
            ],
            challenges=[ChallengeOut.of(s) for s in summary.challenges],
            catalog=[
                EarnRuleOut(
                    kind=rule.key,
                    label=rule.label,
                    coins=rule.coins,
                    daily_cap=rule.daily_cap,
                )
                for rule in reward_rules.RULES.values()
                if rule.coins > 0
            ],
            daily_cap_remaining=summary.daily_cap_remaining,
            review_month=summary.review_month,
            review_claimed=summary.review_claimed,
        )


class ReviewIn(CamelModel):
    month: str


class ReviewOut(CamelModel):
    month: str
    coins_awarded: int
    balance: int
