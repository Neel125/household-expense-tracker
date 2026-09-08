"""Uvicorn entrypoint.

The application is assembled in app/main.py (the MVC factory). This thin
module re-exports it so the familiar command still works:

    uvicorn main:app --reload --port 8000
"""
from app.main import app

__all__ = ["app"]
