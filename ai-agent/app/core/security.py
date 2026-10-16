"""Service-to-service authentication.

The agent service has no notion of end users: the backend authenticates
the person, resolves their household, and calls here with a shared
secret. That keeps tenancy decided in exactly one place — a request that
reaches this service has already been told which household it may read.

An unset token is refused rather than treated as "open". A service that
can read every household's finances must not be reachable by accident.
"""
import hmac

from fastapi import Header, HTTPException

import logging
from app.core.config import settings


def require_service_token(authorization: str | None = Header(default=None)) -> None:
    print(f"settings.service_token: {settings.service_token}")
    print(f"authorization: {authorization}")
    if not settings.service_token:
        raise HTTPException(503, "AGENT_SERVICE_TOKEN is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Not authenticated")
    presented = authorization.split(" ", 1)[1].strip()
    # Constant-time: the token is a fixed secret, so a timing oracle on it
    # is worth closing.
    if not hmac.compare_digest(presented, settings.service_token):
        raise HTTPException(401, "Invalid service token")
