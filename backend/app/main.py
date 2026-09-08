"""Application factory: wire config, middleware, routers, error handling,
and (in production) static serving of the built frontend."""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import init_db
from app.controllers import api_router
from app.services.errors import DomainError


def create_app() -> FastAPI:
    app = FastAPI(title="Ledger & Card API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        # Optional one-time migration of any legacy single-tenant SQLite
        # data into a default household + owner login.
        from app.migrate_legacy import migrate_legacy_data

        migrate_legacy_data()

    # Domain errors -> clean JSON with the right status. FastAPI puts the
    # message under `detail`, matching the frontend's error handling.
    @app.exception_handler(DomainError)
    def _domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

    app.include_router(api_router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """If the frontend has been built, serve it from this same process so a
    single `uvicorn` is a complete deploy."""
    dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
    if not os.path.isdir(dist):
        return
    app.mount("/assets", StaticFiles(directory=os.path.join(dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        candidate = os.path.join(dist, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(dist, "index.html"))


app = create_app()
