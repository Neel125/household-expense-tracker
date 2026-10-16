"""Configuration, read once from the environment.

Mirrors the backend's Settings pattern on purpose: one place reads
os.environ, everything else depends on typed attributes.
"""
import os
from functools import lru_cache
import logging
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(url: str) -> str:
    # Render (and Heroku-style hosts) still emit postgres://.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Settings:
    def __init__(self) -> None:
        # The backend's database, read-only. SQLite default keeps local
        # development a single command; production points at the same
        # Postgres the API writes to.
        self.database_url: str = _normalize_database_url(
            os.environ.get("DATABASE_URL", "sqlite:///../backend/expense_tracker.db")
        )

        # Model. Everything monetary is computed in app/finance; the model
        # only reads those results and writes prose, so a small local
        # model is enough — and keeping it local means a household's
        # ledger never leaves the machine it is hosted on.
        #
        # The model must support tool calling: every figure reaches the
        # model through a typed finance tool, and the structured answer
        # comes back as one more tool call. llama3.1 and qwen3 do;
        # gemma3 does not.
        self.ollama_base_url: str = os.environ.get(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        ).rstrip("/")
        self.agent_model: str = os.environ.get("AGENT_MODEL", "llama3.1:8b")
        self.subagent_model: str = os.environ.get(
            "AGENT_SUBAGENT_MODEL", os.environ.get("AGENT_MODEL", "llama3.1:8b")
        )
        # Ollama's own default context window (2048) is far too small for
        # this agent: the system prompt plus fifteen-odd tool schemas fill
        # it before the books are even read, and Ollama silently drops the
        # oldest tokens rather than erroring. Set it generously.
        self.num_ctx: int = int(os.environ.get("AGENT_NUM_CTX", "16384"))
        # Zero, deliberately: two runs over the same books should not
        # disagree about whether the household is overspending.
        self.temperature: float = float(os.environ.get("AGENT_TEMPERATURE", "0"))

        # Guardrails. A runaway tool loop costs wall-clock time on a
        # local GPU the same way it costs money on a hosted API, so the
        # graph is capped and the whole run is time-bounded. The default
        # is generous because a local 8B model on CPU is slow; the
        # backend's AGENT_RUN_TIMEOUT should be at least this large.
        self.recursion_limit: int = int(os.environ.get("AGENT_RECURSION_LIMIT", "1000"))
        self.timeout_seconds: int = int(os.environ.get("AGENT_TIMEOUT_SECONDS", "600"))

        # Shared secret. The agent service is internal — it answers only
        # to the backend, which has already authenticated the user and
        # resolved their household.
        self.service_token: str = os.environ.get("AGENT_SERVICE_TOKEN", "")
        logging.info(f"AGENT_SERVICE_TOKEN: {self.service_token}")

        self.currency: str = os.environ.get("AGENT_CURRENCY", "INR")
        self.allowed_origins: str = os.environ.get("ALLOWED_ORIGINS", "*")

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def llm_configured(self) -> bool:
        """Ollama needs no key, so there is nothing to be missing — this
        stays as a property because the health endpoint and the /agent
        routes are written against it, and because a deployment that
        points AGENT_OLLAMA at nothing should still answer 503 rather
        than hang."""
        return bool(self.ollama_base_url and self.agent_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
