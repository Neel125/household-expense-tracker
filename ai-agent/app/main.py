"""Application factory for the household finance agent service.

This process answers only to the backend. It authenticates callers with
a shared secret, reads the backend's database without ever writing to
it, and exposes two families of endpoint — deterministic analysis and
agent narrative — under `/capabilities`, `/analysis/*` and `/agent/*`.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.controllers import api_router
from app.core.config import settings
from app.core.database import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("agent-service")


def _check_ollama() -> None:
    """Report at boot whether the configured model is actually there.

    A missing model is the one misconfiguration this service cannot
    detect from its own settings, and it would otherwise show up as a
    404 on a household's first question. This only logs: Ollama may
    still be starting, and a model can be pulled while the service runs,
    so refusing to boot would be wrong.
    """
    # stdlib rather than httpx: this runs once at boot, and httpx is only
    # here transitively through the Ollama client.
    import json  # noqa: PLC0415 - startup-only
    import urllib.request  # noqa: PLC0415 - startup-only

    try:
        with urllib.request.urlopen(
            f"{settings.ollama_base_url}/api/tags", timeout=5.0
        ) as response:
            body = json.load(response)
        available = [m.get("name", "") for m in body.get("models", [])]
    except Exception as exc:  # noqa: BLE001 - logged, not fatal
        log.warning(
            "ollama at %s is not reachable (%s) — /agent/* will fail until it is",
            settings.ollama_base_url,
            type(exc).__name__,
        )
        return

    log.info(
        "model: %s on ollama at %s (num_ctx=%s)",
        settings.agent_model,
        settings.ollama_base_url,
        settings.num_ctx,
    )
    for name in {settings.agent_model, settings.subagent_model}:
        if name not in available:
            log.warning(
                "model %r is not pulled on %s (available: %s) — run `ollama pull %s`",
                name,
                settings.ollama_base_url,
                ", ".join(available) or "none",
                name,
            )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Household Finance Agent",
        version="1.0.0",
        description=(
            "LangChain deep agent over one household's books. Reads the ledger "
            "read-only; every figure is computed in Python and only interpreted "
            "by the model."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        # Fail loudly at boot rather than on the first request. A service
        # that starts healthy and 500s on every call is harder to
        # diagnose than one that refuses to come up.
        if not settings.service_token:
            log.error("AGENT_SERVICE_TOKEN is not set — every request will be refused.")
        if not settings.llm_configured:
            log.warning("No Ollama host configured — /agent/* will return 503.")
        else:
            _check_ollama()
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            log.info("database reachable (read-only)")
        except Exception:  # noqa: BLE001 - logged, not fatal: the DB may lag us at boot
            log.exception("database unreachable at startup")

    @app.get("/health", tags=["meta"])
    def health() -> JSONResponse:
        """Unauthenticated on purpose: this is what the container's health
        check and the platform's probe call. It reports posture, never
        data."""
        database = "ok"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            database = f"error: {type(exc).__name__}"
        healthy = database == "ok"
        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ok" if healthy else "degraded",
                "database": database,
                "llmConfigured": settings.llm_configured,
                "model": settings.agent_model,
            },
        )

    @app.exception_handler(ValueError)
    def _value_error(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    app.include_router(api_router)
    return app


app = create_app()
