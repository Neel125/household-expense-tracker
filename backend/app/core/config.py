"""Application configuration, read once from the environment.

A single Settings object is the one place env vars are read, so the rest
of the code depends on typed attributes rather than os.environ scattered
about (Single Responsibility + easy to override in tests).
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(url: str) -> str:
    # Render (and some Heroku-style hosts) still emit postgres://.
    # SQLAlchemy 1.4+ only accepts postgresql://.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Settings:
    def __init__(self) -> None:
        # SQLite by default so the app runs with zero infra; point
        # DATABASE_URL at Postgres (postgresql://user:pass@host/db) in
        # docker-compose / production / Render.
        self.database_url: str = _normalize_database_url(
            os.environ.get("DATABASE_URL", "sqlite:///./expense_tracker.db")
        )
        self.allowed_origins: str = os.environ.get("ALLOWED_ORIGINS", "*")

        # Auth. CHANGE JWT_SECRET in any real deployment.
        self.jwt_secret: str = os.environ.get(
            "JWT_SECRET", "dev-only-change-me-please-32chars-min"
        )
        self.jwt_algorithm: str = os.environ.get("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = int(
            os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7))
        )
        self.invite_expire_days: int = int(os.environ.get("INVITE_EXPIRE_DAYS", "14"))

        self.seed_data: bool = os.environ.get("SEED_DATA", "false").lower() == "true"

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
